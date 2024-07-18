
from pydantic import BaseModel, SecretStr


class GoodDataConfig(BaseModel):
    host: str
    token: SecretStr


class SnowflakeConfig(BaseModel):
    user: str
    role: str
    password: SecretStr
    account: str
    warehouse: str
    port: str


class SpecificProvisionerConfig(BaseModel):
    gooddata_config: GoodDataConfig
    snowflake_config: SnowflakeConfig
