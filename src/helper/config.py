from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str

    ## postgres
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_MAIN_DB: str

    ## LLM
    GEMINI: str
    COHERE: str

    model_config = SettingsConfigDict(env_file=".env")


def get_settings():
    return Settings()
