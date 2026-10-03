"""Output-side guardrails for Jeli's freeform chat/narrative replies.

Unlike Pazuru's tool-calling advisors (pazuru/backend/services/ai_advisor_guard.py),
Jeli has no tool schema and no discrete "tool called" signal — it's a single freeform
RAG completion over the Pazuru/Tsumi context JSON. Benchmarking 2026-09-24/25 (Plan W)
found two real, reproducible defects in the chosen shared model (qwen2.5:3b-instruct):
it fabricates monetary figures not present in the retrieved context, and it routinely
omits the mandatory disclaimer despite the system prompt requiring it on every
substantive financial answer (jeli_system.txt). This module patches both server-side
rather than depending on model instruction-following alone — the same rationale as
Pazuru's guard, applied to Jeli's different (non-tool-calling) shape.
"""
from __future__ import annotations

import re

# The leading \d+ (not \d{1,3}) is deliberate: found live in prod 2026-09-25 (Plan W
# smoke test against a real account) that a bare 4+-digit figure with no thousands
# separator — e.g. "45230.50", exactly how qwen2.5:3b-instruct writes amounts unless
# told to group them — did not match \d{1,3}-anchored patterns at all, silently
# exempting any real balance over 999.99 from both fabrication-grounding and the
# disclaimer check below. Grouped forms ("1,234.56") still match via the optional
# (?:[.,]\d{3})* groups. Mirrors the identical fix in pazuru's ai_advisor_guard.py.
_MONETARY_RE = re.compile(r"\b\d+(?:[.,]\d{3})*[.,]\d{2}\b")

# Second gap found the same day, running the 18-scenario realistic suite against live
# prod: qwen2.5:3b-instruct routinely drops the trailing zero ("2011.6" not "2011.60")
# or omits the decimal part entirely ("1200") when the figure sits next to a currency
# marker it already wrote — neither form has the 2 decimal digits _MONETARY_RE requires,
# so 6 of 20 real scenarios ("€2011.6", "€1200 per month", "€85.4 per month", "0.0 EUR")
# slipped past both the fabrication check and the disclaimer check. This pass only fires
# when a currency symbol/code is directly adjacent, so it can't start flagging unrelated
# integers (dates, percentages, counts) elsewhere in a reply.
_CCY = r"(?:EUR|USD|GBP|€|\$|£)"
_GROUPED_NUM = r"\d+(?:[.,]\d{3})*(?:[.,]\d{1,2})?"
_CCY_ADJACENT_RE = re.compile(
    rf"{_CCY}\s?({_GROUPED_NUM})|({_GROUPED_NUM})\s?{_CCY}"
)

# Third gap, same investigation: even with the currency-adjacent pass above, grounding
# compared raw strings — so a reply figure normalized from "€2011.6" ("2011.6") was
# never found "verbatim" inside context_text, because /jeli/context serializes the
# identical value as JSON `2011.6` with no adjacent € or "EUR" token at all (it's a
# bare number under a key like "total_balance_eur"). Rather than special-case every
# key-naming convention, context_text is scanned for ALL bare numeric literals — safe
# because context_text is trusted, structured JSON (not freeform prose), so being
# permissive here only ever makes grounding more correct, never less safe — and both
# sides are compared by normalized numeric value rather than raw string, so "2011.6",
# "2011.60", and "2,011.60" all match each other.
_BARE_NUM_RE = re.compile(r"-?\d+(?:[.,]\d{3})*(?:[.,]\d{1,2})?")


def _normalize_figure(raw: str) -> str:
    cleaned = raw.lstrip("-").replace(",", "")
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    try:
        return f"{float(cleaned):.2f}"
    except ValueError:
        return cleaned


DISCLAIMERS = {
    "en": (
        "This is for informational purposes only and does not constitute financial, "
        "investment, or tax advice. Always consult a qualified financial adviser or tax "
        "professional before making financial decisions."
    ),
    "it": (
        "Queste informazioni hanno scopo puramente informativo e non costituiscono consulenza "
        "finanziaria, d'investimento o fiscale. Consulta sempre un consulente finanziario o "
        "fiscale qualificato prima di prendere decisioni."
    ),
    "fr": (
        "Ces informations sont fournies à titre indicatif uniquement et ne constituent pas un "
        "conseil financier, d'investissement ou fiscal. Consultez toujours un conseiller "
        "financier ou fiscal qualifié avant toute décision."
    ),
}
DISCLAIMER = DISCLAIMERS["en"]

_DISCLAIMER_MARKERS = (
    "informational purposes only",
    "scopo puramente informativo",
    "titre indicatif uniquement",
)

# Lines of the system prompt the small model sometimes echoes back verbatim.
_ECHO_RE = re.compile(
    r"^(RULES \(non-negotiable\):|TONE:|EXPERTISE LEVEL:|DISCLAIMER).*$"
    r"|^- (Only answer|Always cite|Never store|Respect privacy|Never recommend|Reply in).*$",
    re.MULTILINE,
)

FABRICATION_REFUSAL = (
    "I don't have a grounded figure for that from your Naforo/Yiriba data right now — "
    "rather than guess, could you check the relevant page directly or rephrase your "
    "question?"
)


def _reply_figures(text: str) -> set[str]:
    raw = set(_MONETARY_RE.findall(text))
    for match in _CCY_ADJACENT_RE.finditer(text):
        num = match.group(1) or match.group(2)
        if num:
            raw.add(num)
    return {_normalize_figure(r) for r in raw}


def _context_figures(text: str) -> set[str]:
    return {_normalize_figure(r) for r in _BARE_NUM_RE.findall(text)}


def sanitize_reply(reply: str, *, context_text: str, lang: str = "en") -> str:
    """Return `reply` unchanged, refused, or with the disclaimer appended.

    Echoed system-prompt lines are stripped first; the disclaimer follows `lang`.
    Two independent checks:
    - every monetary figure in the reply must appear verbatim somewhere in
      `context_text` (the raw Naforo + Yiriba /jeli/context JSON that was fed to the
      model this turn) — a figure the context doesn't back is fabricated
      (found empirically benchmarking qwen2.5:3b-instruct, 21 fabricated figures
      across the Jeli benchmark suite, the highest of any candidate model);
    - a reply containing a monetary figure (the heuristic for "substantive financial
      answer") gets the mandatory disclaimer appended if the model didn't include it
      (qwen2.5:3b-instruct omitted it in every benchmarked response, 0/4 scenarios).
    """
    reply = re.sub(r"\n{3,}", "\n\n", _ECHO_RE.sub("", reply)).strip()
    reply_figures = _reply_figures(reply)
    if reply_figures and not reply_figures.issubset(_context_figures(context_text)):
        return FABRICATION_REFUSAL

    lowered = reply.lower()
    if reply_figures and not any(m in lowered for m in _DISCLAIMER_MARKERS):
        reply = f"{reply.rstrip()}\n\n{DISCLAIMERS.get(lang, DISCLAIMER)}"

    return reply
