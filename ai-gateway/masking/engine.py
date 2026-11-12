"""Mask PII before text leaves the gateway and restore it in the reply.

Fail closed: any analyzer failure raises ``MaskingError`` and the caller must not
send the text to a provider.
"""

import functools
import re
from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from masking.recognizers import (
    COMPANY_SUFFIX,
    LABELS,
    S_KNOWN,
    CounterpartyRecognizer,
    CuePersonRecognizer,
    LabelledRecognizer,
    NerRecognizer,
    StructuredRecognizer,
)

SPACY_MODEL = "it_core_news_lg"


class MaskingError(RuntimeError):
    """Masking could not be completed; the request must not go to a provider."""


@dataclass
class KnownEntities:
    persons: list[str] = field(default_factory=list)
    orgs: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)


def _key(label: str, original: str) -> tuple:
    text = re.sub(r"\s+", " ", original).strip().casefold()
    if label == "AZIENDA":
        text = re.sub(r"[.,]", "", COMPANY_SUFFIX.sub("", original)).strip().casefold()
        text = (
            re.sub(r"\s+", " ", text)
            or re.sub(r"\s+", " ", original).strip().casefold()
        )
    elif label == "PERSONA":
        return (label, tuple(sorted(re.sub(r"[.,]", " ", text).split())))
    elif label in ("IBAN", "CARTA", "CF", "PIVA", "NIR", "CONTO", "TELEFONO"):
        text = re.sub(r"[\s-]", "", text)
    return (label, text)


class Mapping:
    """Bidirectional ``placeholder <-> original``; one original always maps to one placeholder."""

    def __init__(self) -> None:
        self._by_key: dict[tuple, str] = {}
        self._by_ph: dict[tuple[str, int], str] = {}
        self._counters: dict[str, int] = {}

    def placeholder_for(self, label: str, original: str) -> str:
        key = _key(label, original)
        found = self._by_key.get(key)
        if found:
            return found
        n = self._counters.get(label, 0) + 1
        self._counters[label] = n
        ph = f"[{label}_{n}]"
        self._by_key[key] = ph
        self._by_ph[(label, n)] = original
        return ph

    def original(self, placeholder: str) -> str | None:
        m = _PLACEHOLDER.fullmatch(placeholder.strip())
        return self._lookup(m) if m else None

    def _lookup(self, m: re.Match) -> str | None:
        return self._by_ph.get((m.group(1).upper(), int(m.group(2))))

    def __len__(self) -> int:
        return len(self._by_ph)


_LABEL_ALT = "|".join(LABELS)
_PLACEHOLDER = re.compile(
    rf"(?:\[\s*|(?<!\w))({_LABEL_ALT})[_ ]?(\d+)(?:\s*\])?", re.IGNORECASE
)


def unmask(text: str, mapping: Mapping) -> str:
    """Restore originals; unknown placeholders are left untouched."""

    def repl(m: re.Match) -> str:
        return mapping._lookup(m) or m.group(0)

    return _PLACEHOLDER.sub(repl, text)


@functools.lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    nlp = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "it", "model_name": SPACY_MODEL}],
            "ner_model_configuration": {"labels_to_ignore": ["O", "MISC"]},
        }
    ).create_engine()
    registry = RecognizerRegistry(supported_languages=["it"])
    for rec in (
        StructuredRecognizer(),
        LabelledRecognizer(),
        CuePersonRecognizer(),
        CounterpartyRecognizer(),
        NerRecognizer(),
    ):
        registry.add_recognizer(rec)
    return AnalyzerEngine(registry=registry, nlp_engine=nlp, supported_languages=["it"])


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    label: str
    score: float


def _known_spans(text: str, known: KnownEntities) -> list[_Span]:
    spans: list[_Span] = []
    groups = (
        ("PERSONA", known.persons),
        ("AZIENDA", known.orgs),
        ("INDIRIZZO", known.addresses),
    )
    for label, values in groups:
        names: list[str] = []
        for v in values:
            v = (v or "").strip()
            if len(v) < 2:
                continue
            names.append(v)
            parts = v.split()
            if label == "PERSONA" and len(parts) == 2:
                names.append(f"{parts[1]} {parts[0]}")  # "Rossi Mario"
        for name in sorted(set(names), key=len, reverse=True):
            pattern = r"\s+".join(re.escape(p) for p in name.split())
            for m in re.finditer(rf"(?<!\w){pattern}(?!\w)", text, re.IGNORECASE):
                spans.append(_Span(m.start(), m.end(), label, S_KNOWN))
    return spans


def _resolve(spans: list[_Span], text: str) -> list[_Span]:
    """Highest layer first; lower-priority spans keep only their uncovered remainder."""
    accepted: list[_Span] = []
    for sp in sorted(spans, key=lambda s: (-s.score, -(s.end - s.start), s.start)):
        pieces = [(sp.start, sp.end)]
        for a in accepted:
            nxt = []
            for s, e in pieces:
                if a.end <= s or a.start >= e:
                    nxt.append((s, e))
                    continue
                if s < a.start:
                    nxt.append((s, a.start))
                if e > a.end:
                    nxt.append((a.end, e))
            pieces = nxt
        for s, e in pieces:
            chunk = text[s:e]
            stripped = chunk.strip(" \t,;:()")
            if len(stripped) < 2 or not any(c.isalnum() for c in stripped):
                continue
            s2 = s + (len(chunk) - len(chunk.lstrip(" \t,;:()")))
            accepted.append(_Span(s2, s2 + len(stripped), sp.label, sp.score))
    return sorted(accepted, key=lambda s: s.start)


def mask(
    text: str, known: KnownEntities, mapping: Mapping | None = None
) -> tuple[str, Mapping]:
    mapping = mapping if mapping is not None else Mapping()
    if not text or not text.strip():
        return text, mapping
    try:
        results = get_analyzer().analyze(text=text, language="it")
        spans = [_Span(r.start, r.end, r.entity_type, r.score) for r in results]
        spans += _known_spans(text, known)
        resolved = _resolve(spans, text)
        out: list[str] = []
        cursor = 0
        for sp in resolved:
            out.append(text[cursor : sp.start])
            out.append(mapping.placeholder_for(sp.label, text[sp.start : sp.end]))
            cursor = sp.end
        out.append(text[cursor:])
        return "".join(out), mapping
    except MaskingError:
        raise
    except Exception as exc:  # fail closed: never let unmasked text through
        raise MaskingError(f"masking failed: {type(exc).__name__}") from exc


def _mask_value(value, known: KnownEntities, mapping: Mapping):
    if isinstance(value, str):
        return mask(value, known, mapping)[0]
    if isinstance(value, list):
        return [_mask_value(v, known, mapping) for v in value]
    if isinstance(value, dict):
        return {k: _mask_value(v, known, mapping) for k, v in value.items()}
    return value


def mask_messages(
    messages: list[dict], known: KnownEntities
) -> tuple[list[dict], Mapping]:
    """Mask content of every role, tool results, and tool-call arguments."""
    mapping = Mapping()
    out: list[dict] = []
    for msg in messages:
        new = dict(msg)
        content = msg.get("content")
        if isinstance(content, str):
            new["content"] = mask(content, known, mapping)[0]
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    part = {**part, "text": mask(part["text"], known, mapping)[0]}
                parts.append(part)
            new["content"] = parts
        if msg.get("tool_calls"):
            calls = []
            for call in msg["tool_calls"]:
                call = dict(call)
                fn = dict(call.get("function") or {})
                if "arguments" in fn:
                    fn["arguments"] = _mask_value(fn["arguments"], known, mapping)
                call["function"] = fn
                calls.append(call)
            new["tool_calls"] = calls
        if (
            isinstance(msg.get("function_call"), dict)
            and "arguments" in msg["function_call"]
        ):
            fc = dict(msg["function_call"])
            fc["arguments"] = _mask_value(fc["arguments"], known, mapping)
            new["function_call"] = fc
        out.append(new)
    return out, mapping
