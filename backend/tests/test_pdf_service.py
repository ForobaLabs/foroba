import pdf_service


def test_render_pdf_produces_valid_pdf_bytes():
    pdf_bytes = pdf_service.render_pdf(
        year_month="2026-07",
        narrative_text="Income was strong this month.\n\nSpending stayed on budget.",
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
