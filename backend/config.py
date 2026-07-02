from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3.5:latest"
    pazuru_api_url: str = "http://localhost:8000"
    tsumi_api_url: str = "http://localhost:8050"
    jeli_port: int = 8002
    sandbox_image: str = "foroba-sandbox:latest"

    # --- Auth (SP9 / C1) ---
    suite_jwt_secret: str = "dev-insecure-change-me"
    jwt_ttl_minutes: int = 60
    cookie_secure: bool = False           # True behind HTTPS in prod
    auth_db_path: str = "foroba_identity.db"
    seed_mock_users: bool = True
    premium_gating_enabled: bool = True
    onboarding_mifid_enabled: bool = False
    auth_2fa_enabled: bool = False


settings = Settings()
