from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sandbox_image: str = "foroba-sandbox:latest"
    # Shared secret callers send as X-Sandbox-Token (Plan AU M-6). Empty = reject every /run.
    sandbox_runner_token: str = ""

    # Docker-out-of-Docker path resolution: sandbox-runner talks to the HOST's Docker
    # daemon (via docker-socket-proxy), so any `docker run -v <path>:...` it issues is
    # resolved by that daemon against the HOST filesystem, not sandbox-runner's own
    # container filesystem. `workspace_container_dir` is where sandbox-runner itself
    # writes workspace files (a bind mount shared with the host); `workspace_host_dir`
    # is the corresponding absolute HOST path used when building `docker run -v` args
    # for the sandboxed container. Both point at the same bind mount, from each side's
    # own perspective. Set via WORKSPACE_HOST_DIR in docker-compose.yml (found during
    # TI-B item 4 / foroba#120 E2E verification — workspace bind mounts silently
    # resolved to empty dirs on the host without this).
    workspace_container_dir: str = "/tmp/sandbox-workspaces"
    workspace_host_dir: str = "/tmp/sandbox-workspaces"


settings = Settings()
