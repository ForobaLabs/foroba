import sentry_sdk

from observability import init_error_tracking, scrub_event


def test_scrub_event_strips_request_body():
    event = {
        "request": {
            "url": "http://foroba/accounts",
            "method": "POST",
            "data": {"iban": "IT60X0542811101000000123456", "amount": 100},
        },
        "exception": {"values": [{"type": "ValueError"}]},
    }

    result = scrub_event(event, {})

    assert "data" not in result["request"]
    assert result["request"]["url"] == "http://foroba/accounts"
    assert result["exception"]["values"][0]["type"] == "ValueError"


def test_scrub_event_strips_sensitive_breadcrumb_data():
    event = {
        "breadcrumbs": {
            "values": [
                {"category": "http", "data": {"url": "https://enablebanking.com/x"}},
                {"category": "query", "data": {"sql": "SELECT balance FROM accounts"}},
                {"category": "ui.click", "data": {"element": "button"}},
            ]
        }
    }

    result = scrub_event(event, {})

    crumbs = result["breadcrumbs"]["values"]
    assert crumbs[0]["data"] == {}
    assert crumbs[1]["data"] == {}
    assert crumbs[2]["data"] == {"element": "button"}


def test_scrub_event_handles_missing_fields():
    event = {"exception": {"values": [{"type": "RuntimeError"}]}}

    result = scrub_event(event, {})

    assert result == event


def test_init_error_tracking_noops_with_empty_dsn():
    init_error_tracking("")

    assert sentry_sdk.get_client().transport is None
