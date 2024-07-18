from typing import List, Optional

from pydantic import BaseModel

from gooddata_sp.models.api_models import ValidationError
from gooddata_sp.models.data_product_descriptor import DataContract, OutputPort
from gooddata_sp.utility.parsing_pydantic_models import parse_yaml_with_model


class UserDataFilter(BaseModel):
    user: str
    label: str
    value: str
    id: str
    title: str
    operator: Optional[str] = None


class GoodDataOutputPortSpecificSection(BaseModel):
    workspaceId: str
    workspaceName: str
    workspaceLayout: dict
    parentWorkspaceId: Optional[str] = None
    userDataFilters: Optional[List[UserDataFilter]] = None


class GoodDataOutputPort(OutputPort):
    dataContract: DataContract

    def get_specific(self) -> GoodDataOutputPortSpecificSection | ValidationError:
        return parse_yaml_with_model(self.specific, GoodDataOutputPortSpecificSection)
