from typing import Dict, List, Optional

from gooddata_sdk import (
    BasicCredentials,
    CatalogAssigneeIdentifier,
    CatalogAttribute,
    CatalogDataset,
    CatalogDataSource,
    CatalogDataSourcePermissionAssignment,
    CatalogDataSourceSnowflake,
    CatalogDeclarativeDataset,
    CatalogDeclarativeSingleWorkspacePermission,
    CatalogDeclarativeWorkspaceModel,
    CatalogDeclarativeWorkspacePermissions,
    CatalogFact,
    CatalogGenerateLdmRequest,
    CatalogMetric,
    CatalogPdmLdmRequest,
    CatalogPermissionAssignments,
    CatalogScanModelRequest,
    CatalogUser,
    CatalogUserDataFilter,
    CatalogUserDataFilterAttributes,
    CatalogUserDataFilterRelationships,
    CatalogUserGroup,
    CatalogWorkspace,
    CatalogWorkspaceContent,
    GoodDataSdk,
    SnowflakeAttributes,
)

from gooddata_sp.models.config import GoodDataConfig, SnowflakeConfig
from gooddata_sp.models.gooddata import UserDataFilter
from gooddata_sp.models.snowflake import SnowflakeMetadata
from gooddata_sp.utility.logger import get_logger

logger = get_logger(__name__)


class GoodDataClient:
    _gooddata_config: GoodDataConfig
    _snowflake_config: SnowflakeConfig
    _sdk: GoodDataSdk

    def __init__(
        self, gooddata_config: GoodDataConfig, snowflake_config: SnowflakeConfig
    ):
        self._gooddata_config = gooddata_config
        self._snowflake_config = snowflake_config
        self._sdk = GoodDataSdk.create(
            self._gooddata_config.host.rstrip("/"),
            self._gooddata_config.token.get_secret_value(),
        )

    def create_snowflake_datasource(
        self, id: str, name: str, database: str, schema: str
    ) -> CatalogDataSource:
        credentials = BasicCredentials(
            username=self._snowflake_config.user,
            password=self._snowflake_config.password.get_secret_value(),
        )
        snowflake_database_attributes = SnowflakeAttributes(
            account=self._snowflake_config.account,
            warehouse=self._snowflake_config.warehouse,
            db_name=database,
            port=self._snowflake_config.port,
        )
        data_source = CatalogDataSourceSnowflake(
            id=id,
            name=name,
            credentials=credentials,
            schema=schema,
            db_specific_attributes=snowflake_database_attributes,
        )
        self._sdk.catalog_data_source.create_or_update_data_source(
            data_source=data_source
        )
        return self._sdk.catalog_data_source.get_data_source(data_source_id=id)

    def generate_ldm_and_apply_to_workspace(
        self,
        data_source: CatalogDataSource,
        workspace_id: str,
        snowflake_metadata: SnowflakeMetadata,
    ) -> None:
        # scan data source, including views
        scan_request = CatalogScanModelRequest(scan_views=True)
        pdm = self._sdk.catalog_data_source.scan_data_source(
            data_source_id=data_source.id, scan_request=scan_request
        )
        logger.info("Scanned PDM: " + str(pdm))

        if len(pdm.warnings) > 0:
            logger.warn(
                "PDM scan for data source "
                + data_source.id
                + " returned warnings: "
                + str(pdm.warnings)
            )

        # filter out everything that's not from the component at hand
        object_names = list(
            map(lambda object: object.name.upper(), snowflake_metadata.objects)
        )
        filtered_tables = list(
            filter(lambda t: t.id.upper() in object_names, pdm.pdm.tables)
        )
        logger.info("Filtered tables: " + str(filtered_tables))

        # build ldm generate request
        pdm_request = CatalogPdmLdmRequest(tables=filtered_tables)
        ldm_request = CatalogGenerateLdmRequest(
            pdm=pdm_request, workspace_id=workspace_id
        )

        # generate ldm for datasource
        generated_ldm = self._sdk.catalog_data_source.generate_logical_model(
            data_source_id=data_source.id, generate_ldm_request=ldm_request
        )
        logger.info("Generated LDM: " + str(generated_ldm))

        # merge with existing ldm
        # TODO actually merge, we just replace for now, but merge is needed to support multiple dependent components
        current_cdm = self._sdk.catalog_workspace_content.get_declarative_ldm(
            workspace_id=workspace_id
        )
        current_ldm = current_cdm.ldm
        logger.info("Current LDM: " + str(current_ldm))
        updated_cdm = generated_ldm

        self._sdk.catalog_workspace_content.put_declarative_ldm(
            workspace_id=workspace_id, ldm=updated_cdm
        )
        return None

    def set_data_source_permissions(
        self, data_source_id: str, user_ids: List[str], group_ids: List[str], level: str
    ) -> None:
        logger.info(
            "Updating permissions for data source "
            + str(data_source_id)
            + " for users "
            + str(user_ids)
            + " and groups "
            + str(group_ids)
            + " to "
            + level
        )
        for user_id in user_ids:
            current_permissions = self._sdk.catalog_user.get_user_permissions(
                user_id=user_id
            )
            logger.info("Current user permissions: " + str(current_permissions))

            # compute updated permissions
            current_data_source_permissions = current_permissions.data_sources
            filtered_data_source_permissions = [
                p for p in current_data_source_permissions if p.id != data_source_id
            ]
            new_data_source_permission = CatalogDataSourcePermissionAssignment(
                id=data_source_id, permissions=[level]
            )
            updated_data_source_permissions = filtered_data_source_permissions + [
                new_data_source_permission
            ]
            updated_permissions = CatalogPermissionAssignments(
                workspaces=current_permissions.workspaces,
                data_sources=updated_data_source_permissions,
            )

            logger.info("Updated user permissions: " + str(updated_permissions))
            self._sdk.catalog_user.manage_user_permissions(
                user_id=user_id, permission_assignments=updated_permissions
            )

        for group_id in group_ids:
            current_permissions = self._sdk.catalog_user.get_user_group_permissions(
                user_group_id=group_id
            )
            logger.info("Current group permissions: " + str(current_permissions))

            # compute updated permissions
            current_data_source_permissions = current_permissions.data_sources
            filtered_data_source_permissions = [
                p for p in current_data_source_permissions if p.id != data_source_id
            ]
            new_data_source_permission = CatalogDataSourcePermissionAssignment(
                id=data_source_id, permissions=[level]
            )
            updated_data_source_permissions = filtered_data_source_permissions + [
                new_data_source_permission
            ]
            updated_permissions = CatalogPermissionAssignments(
                workspaces=current_permissions.workspaces,
                data_sources=updated_data_source_permissions,
            )

            logger.info("Updated group permissions: " + str(updated_permissions))
            self._sdk.catalog_user.manage_user_group_permissions(
                user_group_id=group_id, permission_assignments=updated_permissions
            )

    def workspace_exists(self, id: str) -> bool:
        workspaces = self._sdk.catalog_workspace.list_workspaces()
        workspace_ids = map(lambda x: x.id, workspaces)
        return id in workspace_ids

    def create_workspace(
        self, id: str, name: str, parent: Optional[str]
    ) -> CatalogWorkspace:
        workspace = CatalogWorkspace(workspace_id=id, name=name, parent_id=parent)
        self._sdk.catalog_workspace.create_or_update(workspace)
        return self._sdk.catalog_workspace.get_workspace(workspace_id=id)

    def export_workspace(self, id: str) -> CatalogDeclarativeWorkspaceModel:
        return self._sdk.catalog_workspace.get_declarative_workspace(id)

    def import_workspace(
        self, id: str, content: CatalogDeclarativeWorkspaceModel
    ) -> None:
        return self._sdk.catalog_workspace.put_declarative_workspace(id, content)

    def empty_workspace(self, id: str) -> None:
        return self._sdk.catalog_workspace.put_declarative_workspace(id, EMPTY_CONTENT)

    def delete_workspace(self, id: str) -> None:
        self._sdk.catalog_workspace.delete_workspace(id)

    def add_or_update_workspace_permissions(
        self, user_ids: List[str], group_ids: List[str], workspace_id: str, level: str
    ) -> None:
        existing_catalog_permissions = (
            self._sdk.catalog_permission.get_declarative_permissions(
                workspace_id=workspace_id
            )
        )
        logger.info(
            "Existing permissions for workspace "
            + workspace_id
            + ": "
            + str(existing_catalog_permissions)
        )

        # compute updated permissions
        existing_permissions = existing_catalog_permissions.permissions
        filtered_existing_permissions = [
            x
            for x in existing_permissions
            if x.assignee.id not in user_ids and x.assignee.id not in group_ids
        ]
        additional_user_permissions = [
            CatalogDeclarativeSingleWorkspacePermission(
                name=level, assignee=CatalogAssigneeIdentifier(id=user_id, type="user")
            )
            for user_id in user_ids
        ]
        additional_group_permissions = [
            CatalogDeclarativeSingleWorkspacePermission(
                name=level,
                assignee=CatalogAssigneeIdentifier(id=group_id, type="userGroup"),
            )
            for group_id in group_ids
        ]
        new_permissions = (
            additional_user_permissions
            + additional_group_permissions
            + filtered_existing_permissions
        )
        new_catalog_permissions = CatalogDeclarativeWorkspacePermissions(
            permissions=new_permissions,
            hierarchy_permissions=existing_catalog_permissions.hierarchy_permissions,
        )

        logger.info(
            "New permissions for workspace "
            + workspace_id
            + ": "
            + str(new_catalog_permissions)
        )
        self._sdk.catalog_permission.put_declarative_permissions(
            workspace_id, new_catalog_permissions
        )

    def remove_workspace_permissions(self, workspace_id: str) -> None:
        existing_catalog_permissions = (
            self._sdk.catalog_permission.get_declarative_permissions(
                workspace_id=workspace_id
            )
        )
        logger.info(
            "Existing permissions for workspace "
            + workspace_id
            + ":"
            + str(existing_catalog_permissions)
        )

        # compute updated (ie empty) permissions
        new_catalog_permissions = CatalogDeclarativeWorkspacePermissions(
            permissions=[],
            hierarchy_permissions=existing_catalog_permissions.hierarchy_permissions,
        )

        logger.info(
            "New permissions for workspace "
            + workspace_id
            + ":"
            + str(new_catalog_permissions)
        )
        self._sdk.catalog_permission.put_declarative_permissions(
            workspace_id, new_catalog_permissions
        )

    def add_user_data_filter(
        self, user_data_filter: UserDataFilter, workspace_id: str
    ) -> CatalogUserDataFilter:
        witboost_user = user_data_filter.user
        gooddata_user = self.map_users(witboost_users=[witboost_user]).get(
            witboost_user
        )
        if gooddata_user is None:
            raise ValueError(
                "Unable to map User Data Filter user "
                + witboost_user
                + " to a GoodData user."
            )

        user_data_filter_relationships = (
            CatalogUserDataFilterRelationships.create_user_user_group_relationship(
                user_id=gooddata_user
            )
        )
        operator = (
            "=" if user_data_filter.operator is None else user_data_filter.operator
        )
        maql = (
            "{label/"
            + user_data_filter.label
            + "} "
            + operator
            + ' "'
            + user_data_filter.value
            + '"'
        )
        user_data_filter_attributes = CatalogUserDataFilterAttributes(
            maql=maql, title=user_data_filter.title
        )
        gooddata_user_data_filter = CatalogUserDataFilter(
            id=user_data_filter.id,
            attributes=user_data_filter_attributes,
            relationships=user_data_filter_relationships,
        )

        self._sdk.catalog_workspace.create_or_update_user_data_filter(
            workspace_id=workspace_id, user_data_filter=gooddata_user_data_filter
        )

        return gooddata_user_data_filter

    def remove_user_data_filter_if_exists(
        self, user_data_filter_id: str, workspace_id: str
    ) -> None:
        user_data_filters = self._sdk.catalog_workspace.list_user_data_filters(
            workspace_id=workspace_id
        )

        matching_user_data_filters = [
            udf for udf in user_data_filters if udf.id == user_data_filter_id
        ]

        if len(matching_user_data_filters) > 0:
            self._sdk.catalog_workspace.delete_user_data_filter(
                user_data_filter_id=user_data_filter_id, workspace_id=workspace_id
            )
        else:
            logger.warn(
                "User Data Filter with id "
                + user_data_filter_id
                + " not found, skipping deletion"
            )

        return None

    def remove_user_data_filters(self, workspace_id: str) -> None:
        user_data_filters = self._sdk.catalog_workspace.list_user_data_filters(
            workspace_id=workspace_id
        )

        for udf in user_data_filters:
            udf_id = udf.id
            if udf_id is not None:
                self._sdk.catalog_workspace.delete_user_data_filter(
                    user_data_filter_id=udf_id, workspace_id=workspace_id
                )
            else:  # how would this happen?
                logger.warn(
                    "User Data Filter without id found in workspace "
                    + workspace_id
                    + ": "
                    + str(udf)
                )

    def get_full_catalog(self, workspace_id: str) -> CatalogWorkspaceContent:
        return self._sdk.catalog_workspace_content.get_full_catalog(workspace_id)

    def get_datasets(self, workspace_id: str) -> list[CatalogDataset]:
        return self.get_full_catalog(workspace_id).datasets

    def get_metrics(self, workspace_id: str) -> list[CatalogMetric]:
        return self.get_full_catalog(workspace_id).metrics

    def get_attributes(self, workspace_id: str) -> list[CatalogAttribute]:
        return self.get_full_catalog(workspace_id).attributes

    def get_facts(self, workspace_id: str) -> list[CatalogFact]:
        return self.get_full_catalog(workspace_id).facts

    def get_host(self) -> str:
        return self._gooddata_config.host

    def get_users(self) -> List[CatalogUser]:
        return self._sdk.catalog_user.list_users()

    def get_groups(self) -> List[CatalogUserGroup]:
        return self._sdk.catalog_user.list_user_groups()

    def map_users(self, witboost_users: List[str]) -> Dict[str, str | None]:
        catalog_users = self.get_users()

        # create a map from witboost-style user refs to gooddata user ids
        witboost_users_to_gooddata_id = {}
        for catalog_user in catalog_users:
            try:
                email = catalog_user.attributes.email  # type: ignore
            except AttributeError:
                email = None

            if email is None:
                logger.warn("GoodData user " + str(catalog_user) + " is missing email")
            else:
                key = "user:" + email.replace("@", "_")
                value = catalog_user.id
                witboost_users_to_gooddata_id[key] = value

        # map identities
        mapped_identities = {}
        for witboost_user in witboost_users:
            gooddata_id = witboost_users_to_gooddata_id.get(witboost_user)

            if gooddata_id is None:
                logger.warn(
                    "Witboost user "
                    + witboost_user
                    + " could not be mapped to a GoodData user"
                )

            mapped_identities[witboost_user] = gooddata_id

        return mapped_identities

    def map_groups(self, witboost_groups: List[str]) -> Dict[str, str | None]:
        catalog_groups = self.get_groups()

        # create a map from witboost-style group refs to gooddata group ids
        witboost_groups_to_gooddata_id = {}
        for catalog_group in catalog_groups:
            try:
                name = catalog_group.name  # type: ignore
            except AttributeError:
                name = None

            if name is None:
                logger.warn("GoodData group " + str(catalog_group) + " is missing name")
            else:
                key = "group:" + name
                value = catalog_group.id
                witboost_groups_to_gooddata_id[key] = value

        # map identities
        mapped_identities = {}
        for witboost_group in witboost_groups:
            gooddata_id = witboost_groups_to_gooddata_id.get(witboost_group)

            if gooddata_id is None:
                logger.warn(
                    "Witboost group "
                    + witboost_group
                    + " could not be mapped to a GoodData group"
                )

            mapped_identities[witboost_group] = gooddata_id

        return mapped_identities

    @classmethod
    def _check_dataset_name(
        cls, dataset: CatalogDeclarativeDataset, object_names: List[str]
    ) -> bool:
        if dataset.data_source_table_id is not None:
            return dataset.data_source_table_id.id in object_names
        else:
            return False


# contents of an empty workspace
EMPTY_CONTENT = CatalogDeclarativeWorkspaceModel.from_dict(
    {
        "analytics": {
            "analyticalDashboardExtensions": [],
            "analyticalDashboards": [],
            "attributeHierarchies": [],
            "dashboardPlugins": [],
            "filterContexts": [],
            "metrics": [],
            "visualizationObjects": [],
        },
        "ldm": {"datasets": [], "dateInstances": []},
    }
)
