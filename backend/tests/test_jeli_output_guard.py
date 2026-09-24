"""Tests for Jeli's output-side fabrication/disclaimer guard."""
from jeli_output_guard import DISCLAIMER, FABRICATION_REFUSAL, sanitize_reply


def test_passes_through_text_with_no_monetary_figure():
    reply = sanitize_reply("You have three accounts connected.", context_text="{}")
    assert reply == "You have three accounts connected."


def test_appends_disclaimer_when_missing_on_grounded_figure():
    context = '{"balance_cents": 87965, "display": "879.65 EUR"}'
    reply = sanitize_reply("Your balance is 879.65 EUR.", context_text=context)
    assert reply.startswith("Your balance is 879.65 EUR.")
    assert DISCLAIMER in reply


def test_does_not_duplicate_existing_disclaimer():
    context = '{"display": "879.65 EUR"}'
    reply = sanitize_reply(
        f"Your balance is 879.65 EUR.\n\n{DISCLAIMER}", context_text=context
    )
    assert reply.count(DISCLAIMER) == 1


def test_blocks_figure_not_present_in_context():
    context = '{"display": "879.65 EUR"}'
    reply = sanitize_reply("You'll save 487.65 EUR next month.", context_text=context)
    assert reply == FABRICATION_REFUSAL


def test_blocks_when_any_figure_in_multi_figure_reply_is_unbacked():
    context = '{"display": "879.65 EUR"}'
    reply = sanitize_reply(
        "Your balance is 879.65 EUR and you'll save 487.65 EUR.", context_text=context
    )
    assert reply == FABRICATION_REFUSAL


def test_blocks_fabricated_ungrouped_4digit_figure():
    """Regression for the live-prod gap found 2026-09-25 (Plan W smoke test): a
    figure of 1000.00 or more written without a thousands separator (how
    qwen2.5:3b-instruct writes numbers by default) used to slip past the old
    \\d{1,3}-anchored regex entirely, so an ungrounded balance like this was
    passed straight through with no refusal and no disclaimer."""
    context = '{"display": "879.65 EUR"}'
    reply = sanitize_reply("Your balance is 45230.50 EUR.", context_text=context)
    assert reply == FABRICATION_REFUSAL


def test_appends_disclaimer_on_grounded_ungrouped_4digit_figure():
    context = '{"balance_cents": 4523050, "display": "45230.50 EUR"}'
    reply = sanitize_reply("Your balance is 45230.50 EUR.", context_text=context)
    assert reply.startswith("Your balance is 45230.50 EUR.")
    assert DISCLAIMER in reply


def test_grounds_currency_prefixed_one_decimal_figure_against_bare_context_number():
    """Regression for the live-prod gap found 2026-09-25 running the 18-scenario
    realistic suite: qwen2.5:3b-instruct wrote "Your net worth is €2011.6" while
    /jeli/context carried the identical value as a bare JSON number with no currency
    marker adjacent (`"total_balance_eur": 2011.6`) and no trailing zero. The old
    exact-string grounding check treated these as different figures and refused a
    correct, fully-grounded answer — 6/20 real scenarios hit this in the baseline run."""
    context = '{"total_balance_eur": 2011.6}'
    reply = sanitize_reply("Your net worth is €2011.6.", context_text=context)
    assert reply.startswith("Your net worth is €2011.6.")
    assert DISCLAIMER in reply


def test_grounds_currency_suffixed_bare_integer_figure_against_bare_context_number():
    context = '{"amount_eur": 1200.0}'
    reply = sanitize_reply("Housing is €1200 per month.", context_text=context)
    assert reply.startswith("Housing is €1200 per month.")
    assert DISCLAIMER in reply


def test_still_blocks_currency_adjacent_figure_absent_from_context():
    context = '{"total_balance_eur": 2011.6}'
    reply = sanitize_reply("Your net worth is €9999.9.", context_text=context)
    assert reply == FABRICATION_REFUSAL
