from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    # Must match Pazuru's OLLAMA_LLM_MODEL: the shared VPS Ollama instance has
    # OLLAMA_MAX_LOADED_MODELS=1, so a mismatched pair forces a reload on every
    # cross-app request. Chosen 2026-09-25 (Plan W) against the real production
    # workload (tool-calling + concurrent-user load) — see
    # pazuru/ARCHITECTURE_DECISIONS.md ADR-002 for the full benchmark table. The
    # prior default, phi3.5:latest, crashed the whole Ollama process under load.
    ollama_model: str = "qwen2.5:3b-instruct"

    # --- Subscription billing (BR-12). Off by default: routes return 503 and no
    # tier is ever changed by a payment event until explicitly enabled. ---
    billing_enabled: bool = False
    billing_provider: str = "fake"  # fake | paddle
    paddle_webhook_secret: str = ""
    billing_grace_days: int = 7
    # JSON map plan -> Paddle price id (server-side only; the client never sends a price).
    paddle_price_ids: str = ""
    # Server-side Paddle Billing API key (subscription cancellation on account erasure).
    # Sandbox base by default; set https://api.paddle.com only at live go-live.
    paddle_api_key: str = ""
    paddle_api_base: str = "https://sandbox-api.paddle.com"

    # --- Deployment mode (GL-4.3, foroba#174) ---
    # "hosted" = multi-tenant beta on the VPS: Jeli Lab (arbitrary code-gen sandbox)
    # is hard-disabled regardless of the lab_service_enabled runtime toggle, since
    # it's the highest-risk feature to expose to untrusted internet users.
    # "selfhost" = local/self-hosted single-user install: Jeli Lab follows the
    # normal lab_service_enabled runtime toggle.
    # Breach-runbook kill switch (Contain 2.3): true answers 503 on every sign-in /
    # refresh / step-up endpoint. Set MAINTENANCE_MODE=true and restart the container.
    maintenance_mode: bool = False
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

    # --- Cross-app session handoff (Plan U, pazuru#150) ---
    # PUBLIC browser-facing origins, distinct from pazuru_api_url/tsumi_api_url above
    # (those are internal Docker-network URLs for server-to-server calls). Used to
    # build the redirect target for /auth/handoff/<app> — must match each app's real
    # public domain (VITE_PAZURU_APP_URL/VITE_TSUMI_APP_URL on the frontend side).
    pazuru_app_url: str = "http://localhost:5173"
    tsumi_app_url: str = "http://localhost:5178"
    # Public marketing-site origin; the waitlist confirm endpoint redirects back here.
    site_base_url: str = ""
    jeli_port: int = 8002
    sandbox_image: str = "foroba-sandbox:latest"
    # set only in docker-compose.yml (TI-B item 4, foroba#120)
    sandbox_runner_url: str | None = None
    searxng_url: str = "http://localhost:8080"

    # --- Auth (SP9 / C1, RS256 migration foroba#149) ---
    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    jwt_ttl_minutes: int = 60
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = False  # True behind HTTPS in prod
    auth_db_path: str = "foroba_identity.db"
    seed_mock_users: bool = True
    # premium_gating_enabled is NOT a settings field here (Plan V, pazuru#152):
    # its live value lives exclusively in the runtime_settings DB table via
    # settings_store.py, and a since-removed pydantic default of True here
    # (vs. the store's then-default of "false") was dead code nothing ever
    # read — but it masked the actual disagreement between the two defaults.
    onboarding_mifid_enabled: bool = False
    auth_2fa_enabled: bool = True  # kill-switch only — see auth/router.py login()

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

    # --- Whole-file DB encryption at rest (GL-11.2, foroba#195) ---
    # Separate trust boundary from field_encryption_key (per-column Fernet): this
    # is the SQLCipher passphrase for the entire foroba_identity.db file.
    # Empty = unencrypted (dev default).
    db_encryption_key: str = ""

    # --- Cross-app cookie domain (MFA hardening, foroba#199) ---
    # Empty (default) = host-only cookie, correct for local dev (each app on a different
    # localhost port already receives cookies regardless of domain scoping). Set to a leading-dot
    # domain (e.g. ".pfh.example.com") in hosted prod ONLY IF Pazuru/Tsumi/Foroba are split across
    # subdomains of a shared parent domain — required for suite_session and stepup_* cookies set
    # by Foroba to reach the other two apps' origins.
    cookie_domain: str = ""

    # --- WebAuthn / Passkeys (MFA hardening, foroba#199) ---
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Foroba"
    webauthn_origin: str = "http://localhost:5175"

    # --- Cross-app step-up tokens (MFA hardening, foroba#199) ---
    stepup_ttl_minutes: int = 45
    stepup_refresh_threshold_minutes: int = 15


settings = Settings()
