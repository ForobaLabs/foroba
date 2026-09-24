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

_MONETARY_RE = re.compile(r"\b\d{1,3}(?:[.,]\d{3})*[.,]\d{2}\b")

DISCLAIMER = (
    "This is for informational purposes only and does not constitute financial, "
    "investment, or tax advice. Always consult a qualified financial adviser or tax "
    "professional before making financial decisions."
)

_DISCLAIMER_MARKER = "informational purposes only"

FABRICATION_REFUSAL = (
    "I don't have a grounded figure for that from your Pazuru/Tsumi data right now — "
    "rather than guess, could you check the relevant page directly or rephrase your "
    "question?"
)


def _figures(text: str) -> set[str]:
    return set(_MONETARY_RE.findall(text))


def sanitize_reply(reply: str, *, context_text: str) -> str:
    """Return `reply` unchanged, refused, or with the disclaimer appended.

    Two independent checks:
    - every monetary figure in the reply must appear verbatim somewhere in
      `context_text` (the raw Pazuru + Tsumi /jeli/context JSON that was fed to the
      model this turn) — a figure the context doesn't back is fabricated
      (found empirically benchmarking qwen2.5:3b-instruct, 21 fabricated figures
      across the Jeli benchmark suite, the highest of any candidate model);
    - a reply containing a monetary figure (the heuristic for "substantive financial
      answer") gets the mandatory disclaimer appended if the model didn't include it
      (qwen2.5:3b-instruct omitted it in every benchmarked response, 0/4 scenarios).
    """
    reply_figures = _figures(reply)
    if reply_figures and not reply_figures.issubset(_figures(context_text)):
        return FABRICATION_REFUSAL

    if reply_figures and _DISCLAIMER_MARKER not in reply.lower():
        reply = f"{reply.rstrip()}\n\n{DISCLAIMER}"

    return reply
