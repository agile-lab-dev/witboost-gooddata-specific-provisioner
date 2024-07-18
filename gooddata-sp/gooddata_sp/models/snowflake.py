from abc import ABC, abstractmethod
from enum import StrEnum
from typing import List

from pydantic import BaseModel, Field

from gooddata_sp.models.api_models import ValidationError
from gooddata_sp.models.data_product_descriptor import (
    Component,
    DataContract,
    OpenMetadataColumn,
    OutputPort,
    StorageArea,
)
from gooddata_sp.utility.parsing_pydantic_models import parse_yaml_with_model


class TableAndSchema(BaseModel):
    tableName: str
    schema_: List[OpenMetadataColumn] = Field(..., alias="schema")


class SnowflakeStorageAreaSpecificSection(BaseModel):
    tables: List[TableAndSchema]
    database: str
    schema_: str = Field(..., alias="schema")


class SnowflakeOutputPortSpecificSection(BaseModel):
    viewName: str
    tableName: str
    database: str
    schema_: str = Field(..., alias="schema")


class SnowflakeObjectType(StrEnum):
    TABLE = "TABLE"
    VIEW = "VIEW"


class SnowflakeObject(BaseModel):
    name: str
    schema_: List[OpenMetadataColumn] = Field(..., alias="schema")
    type: SnowflakeObjectType


class SnowflakeMetadata(BaseModel):
    database: str
    schema_: str = Field(..., alias="schema")
    objects: List[SnowflakeObject]


class SnowflakeComponent(ABC, Component):
    @abstractmethod
    def get_snowflake_metadata(self) -> SnowflakeMetadata | ValidationError:
        pass


class SnowflakeStorageArea(StorageArea, SnowflakeComponent):

    def get_specific(self) -> SnowflakeStorageAreaSpecificSection | ValidationError:
        return parse_yaml_with_model(self.specific, SnowflakeStorageAreaSpecificSection)

    def get_snowflake_metadata(self) -> SnowflakeMetadata | ValidationError:
        specific = self.get_specific()
        if isinstance(specific, ValidationError):
            return specific

        objects = map(
            lambda table: SnowflakeObject(name=table.tableName, schema=table.schema_, type=SnowflakeObjectType.TABLE),
            specific.tables
        )

        return SnowflakeMetadata(database=specific.database,
                                 schema=specific.schema_,
                                 objects=objects)


class SnowflakeOutputPort(OutputPort, SnowflakeComponent):
    dataContract: DataContract

    def get_specific(self) -> SnowflakeOutputPortSpecificSection | ValidationError:
        return parse_yaml_with_model(self.specific, SnowflakeOutputPortSpecificSection)

    def get_snowflake_metadata(self) -> SnowflakeMetadata | ValidationError:
        specific = self.get_specific()
        if isinstance(specific, ValidationError):
            return specific

        objects = [
            SnowflakeObject(name=specific.viewName,
                            schema=self.dataContract.schema_,
                            type=SnowflakeObjectType.VIEW)
        ]

        return SnowflakeMetadata(database=specific.database,
                                 schema=specific.schema_,
                                 objects=objects)
