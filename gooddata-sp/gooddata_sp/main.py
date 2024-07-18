from __future__ import annotations

from starlette.responses import Response

from gooddata_sp.app_config import app
from gooddata_sp.check_return_type import check_response
from gooddata_sp.dependencies import (
    GoodDataServiceDep,
    UnpackedProvisioningRequestDep,
    UnpackedUnprovisioningRequestDep,
    UnpackedUpdateAclRequestDep,
)
from gooddata_sp.models.api_models import (
    ProvisioningStatus,
    RequestValidationError,
    ReverseProvisioningRequest,
    ReverseProvisioningStatus,
    SystemErr,
    ValidationError,
    ValidationRequest,
    ValidationResult,
    ValidationStatus,
)
from gooddata_sp.models.gooddata import GoodDataOutputPort
from gooddata_sp.utility.logger import get_logger

logger = get_logger(__name__)


@app.post(
    "/v1/validate",
    response_model=None,
    responses={"200": {"model": ValidationResult}, "500": {"model": SystemErr}},
    tags=["SpecificProvisioner"],
)
def validate(request: UnpackedProvisioningRequestDep, service: GoodDataServiceDep) -> Response:
    """
    Validate a provisioning request
    """

    if isinstance(request, ValidationError):
        return check_response(ValidationResult(valid=False,
                                               error=request))

    data_product, component_id = request

    component = data_product.get_typed_component_by_id(component_id, GoodDataOutputPort)
    logger.info("Validating component with id: " + component_id)
    logger.debug("Validating component: " + str(component))

    if isinstance(component, GoodDataOutputPort):
        resp = service.validate(component, data_product)
    else:
        resp = ValidationResult(valid=False,
                                error=ValidationError(errors=["Component is not of expected type."]))

    return check_response(out_response=resp)

@app.post(
    "/v1/provision",
    response_model=None,
    responses={
        "200": {"model": ProvisioningStatus},
        "202": {"model": str},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def provision(request: UnpackedProvisioningRequestDep, service: GoodDataServiceDep) -> Response:
    """
    Deploy a data product or a single component starting from a provisioning descriptor
    """

    if isinstance(request, ValidationError):
        return check_response(out_response=request)

    data_product, component_id = request

    component = data_product.get_typed_component_by_id(component_id, GoodDataOutputPort)
    logger.info("Provisioning component with id: " + component_id)
    logger.debug("Provisioning component: " + str(component))

    if isinstance(component, GoodDataOutputPort):
        resp = service.provision(component, data_product)
    else:
        resp = ValidationError(errors=["Component is not of expected type."])

    return check_response(out_response=resp)


@app.post(
    "/v1/unprovision",
    response_model=None,
    responses={
        "200": {"model": ProvisioningStatus},
        "202": {"model": str},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def unprovision(request: UnpackedUnprovisioningRequestDep, service: GoodDataServiceDep) -> Response:
    """
    Undeploy a data product or a single component
    given the provisioning descriptor relative to the latest complete provisioning request
    """  # noqa: E501

    if isinstance(request, ValidationError):
        return check_response(out_response=request)

    data_product, component_id, remove_data = request

    component = data_product.get_typed_component_by_id(component_id, GoodDataOutputPort)
    logger.info("Unprovisioning component with id: " + component_id)
    logger.debug("Unprovisioning component: " + str(component))

    if isinstance(component, GoodDataOutputPort):
        resp = service.unprovision(component, data_product, remove_data)
    else:
        resp = ValidationError(errors=["Component is not of expected type."])

    return check_response(out_response=resp)


@app.post(
    "/v1/reverse-provisioning",
    response_model=None,
    responses={
        "200": {"model": ReverseProvisioningStatus},
        "202": {"model": str},
        "400": {"model": RequestValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def runReverseProvisioning(request: ReverseProvisioningRequest, service: GoodDataServiceDep) -> Response:
    """
    Undeploy a data product or a single component
    given the provisioning descriptor relative to the latest complete provisioning request
    """  # noqa: E501

    logger.info("Reverse provisioning for template: " + str(request.useCaseTemplateId))
    logger.info("Environment: " + str(request.environment))
    logger.info("Parameters: " + str(request.params))

    resp = service.reverse_provision(request.useCaseTemplateId,
                                     request.environment,
                                     request.params,
                                     request.catalogInfo)

    return check_response(out_response=resp)


@app.post(
    "/v1/updateacl",
    response_model=None,
    responses={
        "200": {"model": ProvisioningStatus},
        "202": {"model": str},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def updateacl(request: UnpackedUpdateAclRequestDep, service: GoodDataServiceDep) -> Response:
    """
    Request the access to a specific provisioner component
    """

    if isinstance(request, ValidationError):
        return check_response(out_response=request)

    data_product, component_id, witboost_users = request

    component = data_product.get_typed_component_by_id(component_id, GoodDataOutputPort)
    logger.info("Updating ACL for component with id: " + component_id)
    logger.debug("Updating ACL for component: " + str(component))

    if isinstance(component, GoodDataOutputPort):
        resp = service.update_acl(component, data_product, witboost_users)
    else:
        resp = ValidationError(errors=["Component is not of expected type."])

    return check_response(out_response=resp)


@app.get(
    "/v1/provision/{token}/status",
    response_model=None,
    responses={
        "200": {"model": ProvisioningStatus},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def get_status(token: str) -> Response:
    """
    Get the status for a provisioning request
    """

    # todo: define correct response
    resp = SystemErr(error="Response not yet implemented")

    return check_response(out_response=resp)


@app.post(
    "/v2/validate",
    response_model=None,
    responses={
        "202": {"model": str},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def async_validate(
    body: ValidationRequest,
) -> Response:
    """
    Validate a deployment request
    """

    # todo: define correct response
    resp = SystemErr(error="Response not yet implemented")

    return check_response(out_response=resp)


@app.get(
    "/v2/validate/{token}/status",
    response_model=None,
    responses={
        "200": {"model": ValidationStatus},
        "400": {"model": ValidationError},
        "500": {"model": SystemErr},
    },
    tags=["SpecificProvisioner"],
)
def get_validation_status(
    token: str,
) -> Response:
    """
    Get the status for a provisioning request
    """

    # todo: define correct response
    resp = SystemErr(error="Response not yet implemented")

    return check_response(out_response=resp)
