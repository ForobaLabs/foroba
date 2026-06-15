from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    pazuru_api_url: str = "http://localhost:8001"
    tsumi_api_url: str = "http://localhost:8050"
    jeli_port: int = 8002


settings = Settings()
