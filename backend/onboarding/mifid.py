"""MiFID-style knowledge & experience questionnaire (informational, NOT advice).

Scoring is deterministic: each answer carries points; total >= EXPERT_THRESHOLD
classifies the user as 'expert', otherwise 'base'. Used only to tailor UI
complexity (progressive disclosure), never to recommend investments.
"""
from __future__ import annotations

EXPERT_THRESHOLD = 7

QUESTIONNAIRE: dict = {
    "disclaimer": (
        "This questionnaire tailors the interface to your experience. "
        "It is not investment advice and does not assess suitability of any product."
    ),
    "questions": [
        {"id": "experience", "text": "Years of investing experience",
         "options": [{"label": "None", "points": 0}, {"label": "< 1 year", "points": 1},
                     {"label": "1–3 years", "points": 2}, {"label": "> 3 years", "points": 3}]},
        {"id": "instruments", "text": "Instruments you have traded",
         "options": [{"label": "None", "points": 0}, {"label": "Funds/ETFs", "points": 1},
                     {"label": "Stocks", "points": 2}, {"label": "Derivatives/crypto", "points": 3}]},
        {"id": "frequency", "text": "Trading frequency",
         "options": [{"label": "Never", "points": 0}, {"label": "A few times/year", "points": 1},
                     {"label": "Monthly+", "points": 2}]},
        {"id": "knowledge", "text": "Familiarity with technical indicators",
         "options": [{"label": "None", "points": 0}, {"label": "Some", "points": 1},
                     {"label": "Confident", "points": 2}]},
        {"id": "risk", "text": "Comfort with volatility/risk",
         "options": [{"label": "Low", "points": 0}, {"label": "Medium", "points": 1},
                     {"label": "High", "points": 2}]},
    ],
}


def score_mifid(answers: dict[str, int]) -> str:
    """answers maps question id -> selected option index. Returns 'base' | 'expert'."""
    total = 0
    for q in QUESTIONNAIRE["questions"]:
        idx = answers[q["id"]]  # raises KeyError if a question is unanswered
        total += q["options"][idx]["points"]
    return "expert" if total >= EXPERT_THRESHOLD else "base"
