import os
from typing import Annotated, Optional, Tuple

import yaml
from fastapi import Depends

from gooddata_sp.client.gooddata_client import GoodDataClient
from gooddata_sp.models.api_models import (
    DescriptorKind,
    ProvisioningRequest,
    UpdateAclRequest,
    ValidationError,
)
from gooddata_sp.models.config import GoodDataConfig, SnowflakeConfig, SpecificProvisionerConfig
from gooddata_sp.models.data_product_descriptor import DataProduct
from gooddata_sp.service.gooddata_service import GoodDataService
from gooddata_sp.utility.logger import get_logger
from gooddata_sp.utility.parsing_pydantic_models import parse_yaml_with_model

logger = get_logger(__name__)


async def unpack_provisioning_request(
    provisioning_request: ProvisioningRequest,
) -> Tuple[DataProduct, str] | ValidationError:
    """
    Unpacks a Provisioning Request.

    This function takes a `ProvisioningRequest` object and extracts relevant information
    to perform provisioning for a data product component.

    Args:
        provisioning_request (ProvisioningRequest): The provisioning request to be unpacked.

    Returns:
        Union[Tuple[DataProduct, str], ValidationError]:
            - If successful, returns a tuple containing:
                - `DataProduct`: The data product for provisioning.
                - `str`: The component ID to provision.
            - If unsuccessful, returns a `ValidationError` object with error details.

    Note:
        - This function expects the `provisioning_request` to have a descriptor kind of `DescriptorKind.COMPONENT_DESCRIPTOR`.
        - It will attempt to parse the descriptor and return the relevant information. If parsing fails or the descriptor kind is unexpected, a `ValidationError` will be returned.

    """  # noqa: E501

    if not provisioning_request.descriptorKind == DescriptorKind.COMPONENT_DESCRIPTOR:
        error = (
            "Expecting a COMPONENT_DESCRIPTOR but got a "
            f"{provisioning_request.descriptorKind} instead; please check with the "
            f"platform team."
        )
        return ValidationError(errors=[error])
    try:
        descriptor_dict = yaml.safe_load(provisioning_request.descriptor)
        data_product = parse_yaml_with_model(descriptor_dict.get("dataProduct"), DataProduct)
        component_to_provision = descriptor_dict.get("componentIdToProvision")

        if isinstance(data_product, DataProduct):
            return data_product, component_to_provision
        elif isinstance(data_product, ValidationError):
            return data_product

        else:
            return ValidationError(
                errors=[
                    "An unexpected error occurred while parsing the provisioning request."  # noqa: E501
                ]
            )

    except Exception as ex:
        return ValidationError(errors=["Unable to parse the descriptor.", str(ex)])


UnpackedProvisioningRequestDep = Annotated[
    Tuple[DataProduct, str] | ValidationError,
    Depends(unpack_provisioning_request),
]


async def unpack_unprovisioning_request(
    provisioning_request: ProvisioningRequest,
) -> Tuple[DataProduct, str, bool] | ValidationError:
    """
    Unpacks a Unprovisioning Request.

    This function takes a `ProvisioningRequest` object and extracts relevant information
    to perform unprovisioning for a data product component.

    Args:
        provisioning_request (ProvisioningRequest): The unprovisioning request to be unpacked.

    Returns:
        Union[Tuple[DataProduct, str, bool], ValidationError]:
            - If successful, returns a tuple containing:
                - `DataProduct`: The data product for provisioning.
                - `str`: The component ID to provision.
                - `bool`: The value of the removeData field.
            - If unsuccessful, returns a `ValidationError` object with error details.

    Note:
        - This function expects the `provisioning_request` to have a descriptor kind of `DescriptorKind.COMPONENT_DESCRIPTOR`.
        - It will attempt to parse the descriptor and return the relevant information. If parsing fails or the descriptor kind is unexpected, a `ValidationError` will be returned.

    """  # noqa: E501

    unpacked_request = await unpack_provisioning_request(provisioning_request)
    remove_data = provisioning_request.removeData if provisioning_request.removeData is not None else False

    if isinstance(unpacked_request, ValidationError):
        return unpacked_request
    else:
        data_product, component_id = unpacked_request
        return data_product, component_id, remove_data


UnpackedUnprovisioningRequestDep = Annotated[
    Tuple[DataProduct, str, bool] | ValidationError,
    Depends(unpack_unprovisioning_request),
]


async def unpack_update_acl_request(
    update_acl_request: UpdateAclRequest,
) -> Tuple[DataProduct, str, list[str]] | ValidationError:
    """
    Unpacks an Update ACL Request.

    This function takes an `UpdateAclRequest` object and extracts relevant information
    to update access control lists (ACL) for a data product.

    Args:
        update_acl_request (UpdateAclRequest): The update ACL request to be unpacked.

    Returns:
        Union[Tuple[DataProduct, str, List[str]], ValidationError]:
            - If successful, returns a tuple containing:
                - `DataProduct`: The data product to update ACL for.
                - `str`: The component ID to provision.
                - `List[str]`: A list of references.
            - If unsuccessful, returns a `ValidationError` object with error details.

    Note:
        This function expects the `update_acl_request` to contain a valid YAML string
        in the 'provisionInfo.request' field. It will attempt to parse the YAML and
        return the relevant information. If parsing fails, a `ValidationError` will
        be returned.

    """  # noqa: E501

    try:
        request = yaml.safe_load(update_acl_request.provisionInfo.request)
        data_product = parse_yaml_with_model(request.get("dataProduct"), DataProduct)
        component_to_provision = request.get("componentIdToProvision")
        if isinstance(data_product, DataProduct):
            return (
                data_product,
                component_to_provision,
                update_acl_request.refs,
            )
        elif isinstance(data_product, ValidationError):
            return data_product
        else:
            return ValidationError(
                errors=[
                    "An unexpected error occurred while parsing the update acl request."
                ]
            )
    except Exception as ex:
        return ValidationError(errors=["Unable to parse the descriptor.", str(ex)])


UnpackedUpdateAclRequestDep = Annotated[
    Tuple[DataProduct, str, list[str]] | ValidationError,
    Depends(unpack_update_acl_request),
]


def get_specific_provisioner_config_from_env() -> SpecificProvisionerConfig:
    config = SpecificProvisionerConfig(
        gooddata_config=GoodDataConfig(
            host=get_env("GOODDATA_HOST"),
            token=get_env("GOODDATA_TOKEN"),
        ),
        snowflake_config=SnowflakeConfig(
            user=get_env("SNOWFLAKE_USER"),
            role=get_env("SNOWFLAKE_ROLE"),
            password=get_env("SNOWFLAKE_PASSWORD"),
            account=get_env("SNOWFLAKE_ORGANIZATION_ACCOUNT"),
            warehouse=get_env("SNOWFLAKE_WAREHOUSE"),
            port=get_env("SNOWFLAKE_PORT", "443"),
        )
    )
    logger.debug("Config: " + str(config))
    return config


SpecificProvisionerConfigDep = Annotated[
    SpecificProvisionerConfig,
    Depends(get_specific_provisioner_config_from_env),
]


def get_gooddata_client(specific_provisioner_config: SpecificProvisionerConfigDep) -> GoodDataClient:
    return GoodDataClient(gooddata_config=specific_provisioner_config.gooddata_config,
                          snowflake_config=specific_provisioner_config.snowflake_config)


GoodDataClientDep = Annotated[
    GoodDataClient,
    Depends(get_gooddata_client),
]


def get_gooddata_service(gooddata_client: GoodDataClientDep) -> GoodDataService:
    return GoodDataService(gooddata_client=gooddata_client)


GoodDataServiceDep = Annotated[
    GoodDataService,
    Depends(get_gooddata_service),
]


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    elif default is not None:
        return default
    else:
        raise ValueError(f"Required environment variable {name} not found.")
