import pytest

from onboarding.mifid import QUESTIONNAIRE, score_mifid


def test_questionnaire_shape():
    assert len(QUESTIONNAIRE["questions"]) == 5
    for q in QUESTIONNAIRE["questions"]:
        assert {"id", "text", "options"} <= q.keys()
        assert all({"label", "points"} <= o.keys() for o in q["options"])


def test_all_low_answers_is_base():
    answers = {q["id"]: 0 for q in QUESTIONNAIRE["questions"]}  # first option each
    assert score_mifid(answers) == "base"


def test_all_high_answers_is_expert():
    answers = {q["id"]: len(q["options"]) - 1 for q in QUESTIONNAIRE["questions"]}
    assert score_mifid(answers) == "expert"


def test_threshold_boundary():
    # total points >= 7 -> expert (see implementation)
    # craft answers summing to exactly 7
    answers = {"experience": 2, "instruments": 2, "frequency": 1, "knowledge": 1, "risk": 1}
    assert score_mifid(answers) == "expert"
    answers["risk"] = 0  # total 6
    assert score_mifid(answers) == "base"


def test_missing_answer_raises():
    with pytest.raises(KeyError):
        score_mifid({"experience": 1})
