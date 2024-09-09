from textwrap import shorten
from typing import Dict, List, Optional, Tuple

from gooddata_sdk import CatalogDeclarativeWorkspaceModel

from gooddata_sp.client.gooddata_client import GoodDataClient
from gooddata_sp.models.api_models import (
    ErrorMoreInfo,
    Info,
    ProvisioningStatus,
    RequestValidationError,
    ReverseProvisioningStatus,
    Status1,
    SystemErr,
    ValidationError,
    ValidationResult,
)
from gooddata_sp.models.data_product_descriptor import Component, ComponentKind, DataProduct
from gooddata_sp.models.gooddata import GoodDataOutputPort
from gooddata_sp.models.snowflake import SnowflakeComponent, SnowflakeOutputPort, SnowflakeStorageArea
from gooddata_sp.service.service import SpecificProvisionerService
from gooddata_sp.utility.logger import get_logger

logger = get_logger(__name__)


class GoodDataService(SpecificProvisionerService[GoodDataOutputPort]):

    _gooddata_client: GoodDataClient

    def __init__(self, gooddata_client: GoodDataClient):
        self._gooddata_client = gooddata_client

    def validate(self,
                 component: GoodDataOutputPort,
                 data_product: DataProduct) -> ValidationResult | SystemErr:
        logger.info("Validating component: " + shorten(str(component), 1024))

        specific_section = component.get_specific()
        if isinstance(specific_section, ValidationError):
            return ValidationResult(valid=False,
                                    error=ValidationError(
                                        errors=["Unable to access specific section of component."] +
                                               specific_section.errors))

        try:
            # basic validation
            # round trip from dict to model back to dict, check that everything is equal
            # if not it means the original dict was likely bad
            contents = CatalogDeclarativeWorkspaceModel.from_dict(specific_section.workspaceLayout)
            contents_dict = contents.to_dict()
            if specific_section.workspaceLayout == contents_dict:
                logger.info("Workspace contents: " + shorten(str(contents), 1024))
            else:
                return ValidationResult(valid=False, error=ValidationError(errors=["Workspace content is not valid."]))
        except Exception as ex:
            return ValidationResult(valid=False,
                                    error=ValidationError(errors=["Unable to parse the workspace content.", str(ex)]))

        return ValidationResult(valid=True)

    def provision(self,
                  component: GoodDataOutputPort,
                  data_product: DataProduct) -> ProvisioningStatus | ValidationError | SystemErr:
        logger.info("Provisioning component: " + shorten(str(component), 1024))

        specific_section = component.get_specific()
        if isinstance(specific_section, ValidationError):
            return ValidationError(errors=["Unable to access specific section of component."]
                                   + specific_section.errors)

        workspace_id = specific_section.workspaceId

        mapped_owner_developers = self._map_dp_owner_dev_group(data_product)
        if isinstance(mapped_owner_developers, ValidationError):
            return ValidationError(errors=["Unable to map DP owner and/or developer group to GoodData ids. "
                                           "Ensure they are present in GoodData and try again."]
                                   + mapped_owner_developers.errors)
        dp_owner_gooddata_id, dp_developers_gooddata_id = mapped_owner_developers

        if self._gooddata_client.workspace_exists(workspace_id):
            logger.info("Skipping workspace creation as workspace " + workspace_id + " already exists")
        else:
            logger.info("Creating workspace " + workspace_id)
            self._gooddata_client.create_workspace(workspace_id,
                                                   specific_section.workspaceName,
                                                   specific_section.parentWorkspaceId)

        # populate content, data source, ldm only if it is not a child workspace
        if specific_section.parentWorkspaceId is None:
            workspace_content = CatalogDeclarativeWorkspaceModel.from_dict(specific_section.workspaceLayout)

            logger.info("Importing content to workspace " + workspace_id)
            self._gooddata_client.import_workspace(workspace_id, workspace_content)

            logger.info("Looking for Snowflake dependency...")
            has_snowflake_dependency = self._find_snowflake_dependencies(component, data_product)
            if has_snowflake_dependency:
                logger.info("Snowflake component found; provisioning Data Source and LDM...")
                self._provision_data_source_and_ldm(component,
                                                    workspace_id,
                                                    workspace_content,
                                                    data_product,
                                                    dp_owner_gooddata_id,
                                                    dp_developers_gooddata_id)
            else:
                logger.info("No Snowflake component found; skipping provisioning of Data Source and LDM")

        logger.info("Applying MANAGE permissions to workspace " + workspace_id + " for DP owner and dev group")
        self._gooddata_client.add_or_update_workspace_permissions(user_ids=[dp_owner_gooddata_id],
                                                                  group_ids=[dp_developers_gooddata_id],
                                                                  workspace_id=workspace_id,
                                                                  level='MANAGE')

        logger.info("Removing existing User Data Filters from workspace " + workspace_id)
        self._gooddata_client.remove_user_data_filters(workspace_id)

        if specific_section.userDataFilters is not None:
            logger.info("Applying new User Data Filters to workspace " + workspace_id)
            for user_data_filter in specific_section.userDataFilters:
                logger.info("Applying User Data Filter " + str(user_data_filter) + " to workspace " + workspace_id)
                self._gooddata_client.add_user_data_filter(user_data_filter=user_data_filter, workspace_id=workspace_id)
        else:
            logger.info("No User Data Filters defined for workspace " + workspace_id + ", skipping applying UDF")

        return ProvisioningStatus(
            status=Status1.COMPLETED,
            result="Provisioning completed",
            info=Info(
                publicInfo={
                    "link": {
                        "type": "string",
                        "label": "Link",
                        "value": "Go to \"" + specific_section.workspaceName + "\" workspace on GoodData",
                        "href": self._get_url(workspace_id)
                    }
                },
                privateInfo={}
            )
        )

    def unprovision(self,
                    component: GoodDataOutputPort,
                    data_product: DataProduct,
                    remove_data: bool) -> ProvisioningStatus | ValidationError | SystemErr:
        logger.info("Unprovisioning component: " + shorten(str(component), 1024))

        specific_section = component.get_specific()
        if isinstance(specific_section, ValidationError):
            return ValidationError(errors=["Unable to access specific section of component."] + specific_section.errors)

        id = specific_section.workspaceId

        if self._gooddata_client.workspace_exists(id):
            if remove_data:
                logger.info("Emptying workspace " + id + " as remove_data is true")
                self._gooddata_client.empty_workspace(id)
            else:
                logger.info("Not emptying workspace " + id + " as remove_data is false")

            logger.info("Removing all permissions on workspace " + id)
            self._gooddata_client.remove_workspace_permissions(workspace_id=id)

            return ProvisioningStatus(
                status=Status1.COMPLETED,
                result="Unprovisioning completed",
            )
        else:
            logger.info("Skipping unprovisioning as workspace " + id + " does not exist")

            return ProvisioningStatus(
                status=Status1.COMPLETED,
                result="Unprovisioning completed (nothing to be done)",
            )

    def reverse_provision(self,
                          use_case_template_id: str,
                          environment: str,
                          parameters: Optional[Dict],
                          catalog_info: Optional[Dict])\
            -> ReverseProvisioningStatus | RequestValidationError | SystemErr:
        logger.info("Reverse provisioning for parameters: " + shorten(str(parameters), 1024))

        if parameters is None:
            return RequestValidationError(
                errors=["Missing parameters object in reverse provisioning request"],
                input=None,
                inputErrorField=None,
                userMessage="Missing required parameters for reverse provisioning request",
                moreInfo=ErrorMoreInfo(problems=["Missing required parameters for reverse provisioning request"],
                                       solutions=["Specify required parameters for reverse provisioning request",
                                                  "Contact the Platform Team for further assistance"])
            )

        id = parameters["workspaceId"]

        if id is None or id == "":
            return RequestValidationError(
                errors=["Missing workspaceId in reverse provisioning request"],
                input=None,
                inputErrorField=None,
                userMessage="Missing required parameter workspaceId for reverse provisioning request",
                moreInfo=ErrorMoreInfo(
                    problems=["Missing required parameter workspaceId for reverse provisioning request"],
                    solutions=["Specify workspaceId for reverse provisioning request",
                               "Contact the Platform Team for further assistance"])
            )

        if self._gooddata_client.workspace_exists(id):
            logger.info("Exporting content from workspace " + id)
            content = self._gooddata_client.export_workspace(id)

            return ReverseProvisioningStatus(
                status=Status1.COMPLETED,
                result="Reverse provisioning completed",
                updates={
                    "spec.mesh.specific.workspaceLayout": content.to_dict()
                }
            )
        else:
            error_message = "Workspace " + id + " does not exist"
            logger.error(error_message)

            return RequestValidationError(
                errors=[error_message],
                input=None,
                inputErrorField=None,
                userMessage=error_message,
                moreInfo=ErrorMoreInfo(
                    problems=[error_message],
                    solutions=["Ensure the workspace id provided is correct",
                               "Contact the Platform Team for further assistance"])
            )

    def update_acl(self,
                   component: GoodDataOutputPort,
                   data_product: DataProduct,
                   refs: list[str]) -> ProvisioningStatus | ValidationError | SystemErr:
        logger.info("Update ACL for component: " + shorten(str(component), 1024))

        specific_section = component.get_specific()
        if isinstance(specific_section, ValidationError):
            return ValidationError(errors=["Unable to access specific section of component."] +
                                          specific_section.errors)

        id = specific_section.workspaceId

        if self._gooddata_client.workspace_exists(id):
            logger.info("Removing all permissions on workspace " + id)
            self._gooddata_client.remove_workspace_permissions(workspace_id=id)

            mapped_owner_developers = self._map_dp_owner_dev_group(data_product)
            if isinstance(mapped_owner_developers, ValidationError):
                return ValidationError(errors=["Unable to map DP owner and/or developer group to GoodData ids."]
                                              + mapped_owner_developers.errors)
            dp_owner_gooddata_id, dp_developers_gooddata_id = mapped_owner_developers

            logger.info("Applying MANAGE permissions to workspace " + id + " for DP owner and dev group")
            self._gooddata_client.add_or_update_workspace_permissions(user_ids=[dp_owner_gooddata_id],
                                                                      group_ids=[dp_developers_gooddata_id],
                                                                      workspace_id=id,
                                                                      level='MANAGE')

            user_refs = [user_ref for user_ref in refs if user_ref.startswith("user:")]
            mapped_users = self._gooddata_client.map_users(witboost_users=user_refs)
            valid_users = [v for k, v in mapped_users.items() if v is not None]
            invalid_users = [k for k, v in mapped_users.items() if v is None]

            group_refs = [group_ref for group_ref in refs if group_ref.startswith("group:")]
            mapped_groups = self._gooddata_client.map_groups(witboost_groups=group_refs)
            valid_groups = [v for k, v in mapped_groups.items() if v is not None]
            invalid_groups = [k for k, v in mapped_groups.items() if v is None]

            logger.info("Applying VIEW permissions to workspace " + id + " for consumers")
            self._gooddata_client.add_or_update_workspace_permissions(user_ids=valid_users,
                                                                      group_ids=valid_groups,
                                                                      workspace_id=id,
                                                                      level='VIEW')

            if len(invalid_users) == 0 and len(invalid_groups) == 0:
                return ProvisioningStatus(
                    status=Status1.COMPLETED,
                    result="Update ACL completed",
                )
            else:
                return ProvisioningStatus(
                    status=Status1.FAILED,
                    result="Update ACL failed, unable to map all users/groups. " +
                           "Problematic users: " + str(invalid_users) + ", groups: " + str(invalid_groups),
                )
        else:
            return ProvisioningStatus(
                status=Status1.FAILED,
                result="Update ACL failed, workspace " + id + " does not exist."
            )

    def _get_url(self, id: str) -> str:
        return self._gooddata_client.get_host() + "/dashboards/#/workspace/" + id + "/"

    @staticmethod
    def _compute_data_source_id(component: Component, dependent_component: Component) -> str:
        component_id = component.id
        dependent_component_id = dependent_component.id
        prefix = component_id.split(":")[3:]
        base = ["datasource"]
        suffix = dependent_component_id.split(":")[6:]
        data_source_id = "_".join(prefix + base + suffix)
        return data_source_id

    def _compute_data_source_name(self, component: Component, dependent_component: Component) -> str:
        component_fully_qualified_name = component.fullyQualifiedName
        if component_fully_qualified_name is None:
            component_fully_qualified_name = self._compute_fully_qualified_name(component)
        dependent_component_name = dependent_component.name
        data_source_name = component_fully_qualified_name + " - Data Source - " + dependent_component_name
        return data_source_name

    def _compute_fully_qualified_name(self, component: Component) -> str:
        component_id = component.id
        pieces = component_id.split(":")
        domain = self._rebuild_name_from_normalized_string(pieces[3])
        data_product_name = self._rebuild_name_from_normalized_string(pieces[4])
        data_product_major_version = pieces[5]
        return domain + " - " + data_product_name + " - V" + data_product_major_version + " - " + component.name

    def _provision_data_source_and_ldm(self,
                                       component: GoodDataOutputPort,
                                       workspace_id: str,
                                       workspace_content: CatalogDeclarativeWorkspaceModel,
                                       data_product: DataProduct,
                                       dp_owner_gooddata_id: str,
                                       dp_developers_gooddata_id: str):
        snowflake_component = self._extract_snowflake_dependency(component, data_product)
        if isinstance(snowflake_component, ValidationError):
            return ValidationError(errors=["Unable to extract Snowflake dependencies."] + snowflake_component.errors)

        snowflake_metadata = snowflake_component.get_snowflake_metadata()
        if isinstance(snowflake_metadata, ValidationError):
            return ValidationError(errors=["Unable to extract Snowflake metadata."] + snowflake_metadata.errors)

        data_source_id = self._compute_data_source_id(component, snowflake_component)
        data_source_name = self._compute_data_source_name(component, snowflake_component)
        logger.info("Creating data source " + data_source_id)
        data_source = self._gooddata_client.create_snowflake_datasource(id=data_source_id,
                                                                        name=data_source_name,
                                                                        database=snowflake_metadata.database,
                                                                        schema=snowflake_metadata.schema_)

        logger.info("Applying USE permissions to data source " + data_source_id + " for DP owner and dev group")
        self._gooddata_client.set_data_source_permissions(user_ids=[dp_owner_gooddata_id],
                                                          group_ids=[dp_developers_gooddata_id],
                                                          data_source_id=data_source_id,
                                                          level="USE")

        ldm = workspace_content.ldm
        ldm_exists = ldm is not None and (len(ldm.datasets) > 0 or len(ldm.date_instances) > 0)
        if ldm_exists:
            logger.info("Skipping generating LDM for data source " + data_source_id + " as workspace " + workspace_id +
                        " already has an LDM")
        else:
            logger.info("Generating LDM for data source " + data_source_id +
                        " and applying it to workspace " + workspace_id)
            self._gooddata_client.generate_ldm_and_apply_to_workspace(data_source=data_source,
                                                                      workspace_id=workspace_id,
                                                                      snowflake_metadata=snowflake_metadata)

    @staticmethod
    def _rebuild_name_from_normalized_string(normalized: str) -> str:
        return normalized.replace("-", " ").title()

    @staticmethod
    def _find_snowflake_dependencies(component: Component, data_product: DataProduct)\
            -> List[Component] | ValidationError:
        id = component.id
        dependent_component_ids = component.dependsOn
        if len(dependent_component_ids) == 0:
            return ValidationError(errors=["Component " + id + " must have at least one dependency on a Snowflake " +
                                           "component (Storage Area or Output Port) but has none."])
        dependent_components = [data_product.get_component_by_id(dep_id) for dep_id in dependent_component_ids]
        snowflake_dependent_components = [
            dep_cmp for dep_cmp in dependent_components
            if dep_cmp is not None
               and (dep_cmp.kind == ComponentKind.OUTPUTPORT
                    and dep_cmp.useCaseTemplateId == "urn:dmb:utm:snowflake-outputport-template:0.0.0"
                    or
                    dep_cmp.kind == ComponentKind.STORAGE
                    and dep_cmp.useCaseTemplateId == "urn:dmb:utm:snowflake-storage-template:0.0.0")
        ]
        return snowflake_dependent_components

    @staticmethod
    def _extract_snowflake_dependency(component: Component, data_product: DataProduct)\
            -> SnowflakeComponent | ValidationError:
        id = component.id

        snowflake_dependent_components = GoodDataService._find_snowflake_dependencies(component, data_product)
        if isinstance(snowflake_dependent_components, ValidationError):
            return snowflake_dependent_components

        num_snowflake_components = len(snowflake_dependent_components)
        if num_snowflake_components > 1:
            return ValidationError(errors=["Component " + id + " must have exactly one dependency on a Snowflake " +
                                           "component (Storage Area or Output Port) but has " +
                                           str(num_snowflake_components) + ": " + str(snowflake_dependent_components)])

        dependent_component_id = snowflake_dependent_components[0].id

        dependent_component = data_product.get_component_by_id(dependent_component_id)
        if dependent_component is None:  # can't happen but makes mypy happy
            return ValidationError(errors=[
                "Dependency " + dependent_component_id + " was not found"])

        dependent_component_kind = dependent_component.kind
        if dependent_component_kind == ComponentKind.STORAGE:
            snowflake_component = data_product.get_typed_component_by_id(dependent_component_id, SnowflakeStorageArea)
        elif dependent_component_kind == ComponentKind.OUTPUTPORT:
            snowflake_component = data_product.get_typed_component_by_id(dependent_component_id, SnowflakeOutputPort)
        else:  # can't happen but makes mypy happy
            return ValidationError(errors=[
                "Dependency " + dependent_component_id +
                " must be a Snowflake component but is neither a Storage Area nor an Output Port"])

        return snowflake_component

    def _map_dp_owner_dev_group(self, data_product: DataProduct) -> Tuple[str, str] | ValidationError:
        dp_owner = data_product.dataProductOwner
        dp_owner_gooddata_id = self._gooddata_client \
            .map_users([dp_owner]) \
            .get(dp_owner)
        if dp_owner_gooddata_id is None:
            return ValidationError(errors=["Unable to map DP owner \"" + dp_owner + "\" to a GoodData user."])

        dev_group = data_product.devGroup
        dp_developers_gooddata_id = self._gooddata_client \
            .map_groups([dev_group]) \
            .get(dev_group)
        if dp_developers_gooddata_id is None:
            return ValidationError(errors=["Unable to map DP dev group \"" + dev_group + "\" to a GoodData group."])

        return dp_owner_gooddata_id, dp_developers_gooddata_id