from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3.5:latest"
    pazuru_api_url: str = "http://localhost:8000"
    tsumi_api_url: str = "http://localhost:8050"
    jeli_port: int = 8002
    sandbox_image: str = "foroba-sandbox:latest"
    # set only in docker-compose.yml (TI-B item 4, foroba#120)
    sandbox_runner_url: str | None = None
    searxng_url: str = "http://localhost:8080"

    # --- Auth (SP9 / C1, RS256 migration foroba#149) ---
    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    jwt_ttl_minutes: int = 60
    cookie_secure: bool = False           # True behind HTTPS in prod
    auth_db_path: str = "foroba_identity.db"
    seed_mock_users: bool = True
    premium_gating_enabled: bool = True
    onboarding_mifid_enabled: bool = False
    auth_2fa_enabled: bool = False

    # --- Observability (TI-B item 2, foroba#153) ---
    glitchtip_dsn: str = ""

    # --- Email (TI-D item 2, foroba#159; real SMTP wiring, foroba#163) ---
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


settings = Settings()
