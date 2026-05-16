# bot/quote_generator.py
"""
Generates a Titans quotation PDF by stamping dynamic text
directly onto the blank template.

Strategy:
  • Page 1: create a transparent overlay with only the variable fields
            (company, location, quantity, grade, rate) then merge it
            ON TOP of the template page 1 — every logo, border, table
            and static text comes from the original file untouched.
  • Pages 2-4: copied verbatim from the template (Conditions of Sale).

Coordinate note:
  pdfplumber reports y from the TOP of the page.
  reportlab draws y from the BOTTOM of the page.
  Conversion: rl_y = PAGE_HEIGHT - pdfplumber_bottom

Usage:
    from bot.quote_generator import build_quote_pdf
    import io

    buf = io.BytesIO()
    build_quote_pdf(
        out_buf       = buf,
        template_path = "static/quote_template.pdf",
        company       = "Akash",
        location      = "Chennai",
        quantity      = "25",
        grade         = "M25",
        rate          = "5800",
    )
    buf.seek(0)
"""

import io

PAGE_W = 612   # Letter width  (pt)
PAGE_H = 792   # Letter height (pt)


def build_quote_pdf(
    out_buf,
    template_path: str,
    company: str,
    location: str,
    quantity: str,
    grade: str,
    rate: str,
    exec_name: str = "",
) -> None:
    """Stamp filled-in fields onto the Titans quote template."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    from pypdf import PdfReader, PdfWriter

    try:
        qty_f  = float(quantity)
    except (ValueError, TypeError):
        qty_f  = 0.0
    try:
        rate_f = float(rate)
    except (ValueError, TypeError):
        rate_f = 0.0

    DARK = colors.HexColor("#1A1A1A")
    BOLD = "Helvetica-Bold"
    REG  = "Helvetica"

    def rl_y(pdf_bottom: float) -> float:
        """pdfplumber bottom-of-text → reportlab y baseline."""
        return PAGE_H - pdf_bottom

    # ── Transparent overlay page ──────────────────────────────────────────────
    ov_buf = io.BytesIO()
    c = rl_canvas.Canvas(ov_buf, pagesize=(PAGE_W, PAGE_H))

    # Field 1 — Company after "M/s."  (bottom of that text line = 147.4)
    c.setFont(BOLD, 10)
    c.setFillColor(DARK)
    c.drawString(84, rl_y(145), company)

    # Field 2 — Location in "Sub: Quotation for your ___ Project."  (bottom=173.0)
    c.setFont(BOLD, 10)
    c.drawString(164, rl_y(171.0), f"{location} Project.")

    # Field 3 — Quantity value in row 1  (bottom=298.5)
    c.setFont(REG, 9.5)
    c.setFillColor(DARK)
    c.drawString(267, rl_y(298.5), f"{qty_f:.1f} cum")

    # Field 4 — Project Location value in row 2  (bottom=327.8)
    c.drawString(267, rl_y(327.8), location)

    # Field 5 — Grade and Rate value in row 4, bold  (bottom=386.3)
    c.setFont(BOLD, 9.5)
    c.drawString(267, rl_y(386.3), f"({grade}) - Rs.{rate_f:,.0f} (Including GST)")

    # Field 6 — Company after "For" in sign-off block  (bottom=696.3)
    c.setFont(BOLD, 10)
    c.drawString(78, rl_y(694.4), company)

    c.save()
    ov_buf.seek(0)

    # ── Stamp overlay onto template; keep pages 2-4 as-is ─────────────────────
    template  = PdfReader(template_path)
    overlay_r = PdfReader(ov_buf)
    writer    = PdfWriter()

    page1 = template.pages[0]
    page1.merge_page(overlay_r.pages[0])
    writer.add_page(page1)

    for page in template.pages[1:]:
        writer.add_page(page)

    writer.write(out_buf)