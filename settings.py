from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class __Config(BaseSettings):

    model_config = SettingsConfigDict(env_file='.env', extra='allow')
    APP_VERSION:                     str  = Field(...,                      description='')
    APP_ENV:                         str  = Field(default='dev',            description='')
    API_VERSION:                     str  = Field(default='v1',             description='')
    AGENT_VERBOSE:                   bool = Field(...,                      description='')
    CREWAI_TOOLS_ALLOW_UNSAFE_PATHS: bool = Field(...,                      description='')
    GHCR_TOKEN:                      str  = Field(...,                      description='')
    OPENAI_API_KEY:                  str  = Field(...,                      description='')
    OPENAI_MODEL:                    str  = Field(default='openai/gpt-5.5', description='')


Config = __Config()
