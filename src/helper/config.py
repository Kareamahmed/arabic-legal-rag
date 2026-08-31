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
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    GEMINI_APY_KEY: str
    COHERE_API_KEY: str

    GENERATION_MODEL_ID: str
    EMBEDDING_MODEL_ID: str
    EMBEDDING_SIZE: int

    MAX_INPUT_TOKENS: int
    MAX_OUTPUT_TOKENS: int
    TEMPERATURE: float

    
    model_config = SettingsConfigDict(env_file=".env")


def get_settings():
    return Settings()
