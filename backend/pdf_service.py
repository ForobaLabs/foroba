"""On-demand PDF rendering for monthly reports (foroba#159, TI-D item 2).

reportlab is pure-Python — no system binary dependency, safe for the Docker
image. Rendered on-demand only, never cached (spec Non-goals).
"""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

DISCLAIMER = "AI-generated summary, not financial advice — Personal Finance HUB"


def render_pdf(*, year_month: str, narrative_text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Monthly Financial Report — {year_month}", styles["Title"]),
        Spacer(1, 0.5 * cm),
    ]
    for paragraph in (narrative_text or "").split("\n\n"):
        if paragraph.strip():
            story.append(Paragraph(paragraph.strip(), styles["BodyText"]))
            story.append(Spacer(1, 0.3 * cm))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(DISCLAIMER, styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()
