from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderSpec:
    base_url: str
    models: tuple[str, ...]
    needs_account_id: bool = False


PROVIDERS: dict[str, ProviderSpec] = {
    "cloudflare": ProviderSpec(
        "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        ("@cf/meta/llama-4-scout-17b-16e-instruct",),
        needs_account_id=True,
    ),
    "openai": ProviderSpec("https://api.openai.com/v1", ("gpt-4o-mini", "gpt-4o")),
    "anthropic": ProviderSpec(
        "https://api.anthropic.com/v1/", ("claude-haiku-4-5", "claude-sonnet-4-5")
    ),
    "mistral": ProviderSpec(
        "https://api.mistral.ai/v1", ("mistral-small-latest", "mistral-large-latest")
    ),
    "gemini": ProviderSpec(
        "https://generativelanguage.googleapis.com/v1beta/openai",
        ("gemini-2.5-flash", "gemini-2.5-pro"),
    ),
    "openrouter": ProviderSpec(
        "https://openrouter.ai/api/v1",
        ("meta-llama/llama-4-scout", "openai/gpt-4o-mini"),
    ),
}

ALLOWED_HOSTS: frozenset[str] = frozenset(
    urlsplit(spec.base_url).hostname for spec in PROVIDERS.values()
)
