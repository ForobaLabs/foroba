"""Allowed (app, feature) pairs. `*` is the per-app default."""

FEATURES: dict[str, frozenset[str]] = {
    "pazuru": frozenset(
        {
            "chat",
            "debt_advisor",
            "mortgage_advisor",
            "csv_import",
            "payslip",
            "pdf_statement",
            "lab",
        }
    ),
    "tsumi": frozenset({"jeli", "csv_import", "lab"}),
    "foroba": frozenset({"jeli", "monthly_report", "lab"}),
}


def validate(app: str, feature: str) -> None:
    if app not in FEATURES:
        raise ValueError(f"unknown app: {app}")
    if feature != "*" and feature not in FEATURES[app]:
        raise ValueError(f"unknown feature for {app}: {feature}")
