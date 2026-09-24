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
