from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from gooddata_sp.models.api_models import (
    Info,
    ProvisioningStatus,
    RequestValidationError,
    ReverseProvisioningStatus,
    Status1,
    SystemErr,
    ValidationError,
    ValidationResult,
)
from gooddata_sp.models.data_product_descriptor import DataProduct

T = TypeVar("T")


class SpecificProvisionerService(ABC, Generic[T]):

    @abstractmethod
    def validate(self,
                 component: T,
                 data_product: DataProduct) -> ValidationResult | SystemErr:
        # Example OK
        ValidationResult(
            valid=True,
        )

        # Example KO
        ValidationResult(
            valid=False,
            errors=ValidationError(errors=[
                "Validation error 1",
                "Validation error 2"
            ])
        )

        # Example system error
        return SystemErr(error="Not implemented")

    @abstractmethod
    def provision(self,
                  component: T,
                  data_product: DataProduct) -> ProvisioningStatus | ValidationError | SystemErr:
        # Example OK
        ProvisioningStatus(
            status=Status1.COMPLETED,
            result="Provisioning completed",
            info=Info(
                publicInfo={
                    "link": {
                        "type": "string",
                        "label": "Link",
                        "value": "Go to dashboard on GoodData",
                        "href": "http://www.gooddata.com/my/dashboard"
                    }
                },
                privateInfo={}
            )
        )

        # Example KO
        ProvisioningStatus(
            status=Status1.FAILED,
            result="Provisioning failed",
        )

        # Example validation error
        ValidationError(errors=[
            "Validation error 1",
            "Validation error 2"
        ])

        # Example system error
        return SystemErr(error="Not implemented")

    @abstractmethod
    def unprovision(self,
                    component: T,
                    data_product: DataProduct,
                    remove_data: bool) -> ProvisioningStatus | ValidationError | SystemErr:
        # Example OK
        ProvisioningStatus(
            status=Status1.COMPLETED,
            result="Unprovisioning completed",
        )

        # Example KO
        ProvisioningStatus(
            status=Status1.FAILED,
            result="Unprovisioning failed",
        )

        # Example validation error
        ValidationError(errors=[
            "Validation error 1",
            "Validation error 2"
        ])

        # Example system error
        return SystemErr(error="Not implemented")

    @abstractmethod
    def reverse_provision(self,
                          use_case_template_id: str,
                          environment: str,
                          parameters: dict,
                          catalog_info: dict) -> ReverseProvisioningStatus | RequestValidationError | SystemErr:
        # Example OK
        ReverseProvisioningStatus(
            status=Status1.COMPLETED,
            result="Reverse provisioning completed",
            updates={
                "spec.mesh.specific.field": "new_value"
            }
        )

        # Example KO
        ReverseProvisioningStatus(
            status=Status1.FAILED,
            result="Reverse provisioning failed",
            updates={}
        )

        # Example validation error
        ValidationError(errors=[
            "Validation error 1",
            "Validation error 2"
        ])

        return SystemErr(error="Not implemented")

    @abstractmethod
    def update_acl(self,
                   component: T,
                   data_product: DataProduct,
                   refs: list[str]) -> ProvisioningStatus | ValidationError | SystemErr:
        # Example OK
        ProvisioningStatus(
            status=Status1.COMPLETED,
            result="Update ACL completed",
        )

        # Example KO
        ProvisioningStatus(
            status=Status1.FAILED,
            result="Update ACL failed",
        )

        # Example validation error
        ValidationError(errors=[
            "Validation error 1",
            "Validation error 2"
        ])

        # Example system error
        return SystemErr(error="Not implemented")