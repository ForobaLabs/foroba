from dataclasses import dataclass, field
from typing import Literal

ErrorKind = Literal["auth", "quota", "unavailable", "bad_request"]


@dataclass
class ChatRequest:
    messages: list
    model: str
    tools: list | None = None
    json_mode: bool = False
    stream: bool = False
    max_tokens: int | None = None


@dataclass
class ChatResult:
    text: str
    model: str
    tool_calls: list = field(default_factory=list)
    neurons: int = 0


class ProviderError(Exception):
    """Provider failure. The message carries only the kind and HTTP status, never headers, bodies or keys."""

    def __init__(self, kind: ErrorKind, status: int | None = None):
        self.kind = kind
        self.status = status
        super().__init__(
            f"provider error: {kind}" + (f" (HTTP {status})" if status else "")
        )
