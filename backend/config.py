from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "phi3.5:latest"

    # --- Deployment mode (GL-4.3, foroba#174) ---
    # "hosted" = multi-tenant beta on the VPS: Jeli Lab (arbitrary code-gen sandbox)
    # is hard-disabled regardless of the lab_service_enabled runtime toggle, since
    # it's the highest-risk feature to expose to untrusted internet users.
    # "selfhost" = local/self-hosted single-user install: Jeli Lab follows the
    # normal lab_service_enabled runtime toggle.
    deployment_mode: str = "selfhost"

    # --- Jeli Lab hosted re-enablement (foroba#189) ---
    # Even in "hosted" mode, Jeli Lab stays hard-disabled unless this is explicitly set
    # to true. Flip it only after confirming the VPS can sustain
    # lab_sandbox_concurrency_limit concurrent 512MB sandbox containers. Per-request
    # execution is already isolated (ephemeral container, --network none, --read-only,
    # non-root, see sandbox_docker.run_sandbox); this flag + the concurrency cap below
    # guard against multiple simultaneous hosted users exhausting VPS memory.
    lab_hosted_enabled: bool = False
    # Max sandbox containers allowed to run at once across ALL users (lab_service.py).
    # Each container caps at 512MB; keep this low relative to total VPS RAM.
    lab_sandbox_concurrency_limit: int = 3

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

    # --- Offsite backup (TI-E, foroba#172) — Cloudflare R2, no-op when unconfigured ---
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    backup_encryption_passphrase: str = ""

    # --- Field-level encryption at rest (GL-11.3, foroba#192) ---
    # Encrypts sandbox_conversations.content/code (Jeli Lab chat history).
    # Generate once with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    field_encryption_key: str = ""


settings = Settings()
