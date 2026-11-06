"""Certificate PDF (A4 landscape) with a QR code to the public verification page.

Generated on request (about 20 ms) instead of stored: the data is immutable and a
template change then applies everywhere. Text is drawn as plain strings, so a course
title or name can never inject markup.
"""

import io

from django.conf import settings
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PRIMARY = colors.HexColor("#4F46E5")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")


def _fit(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> float:
    while size > 10 and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def render(cert, template=None) -> bytes:
    buf = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setTitle(f"Certificate {cert.verification_code}")
    c.setAuthor("LearnHub")

    c.setStrokeColor(PRIMARY)
    c.setLineWidth(3)
    c.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    c.setLineWidth(0.6)
    c.rect(16 * mm, 16 * mm, width - 32 * mm, height - 32 * mm)

    cx = width / 2
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(cx, height - 40 * mm, "LEARNHUB")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(cx, height - 62 * mm, "Certificate of Completion")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 14)
    c.drawCentredString(cx, height - 78 * mm, "This certifies that")

    name = cert.recipient_name or "Learner"
    size = _fit(c, name, "Helvetica-Bold", 30, width - 80 * mm)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, height - 96 * mm, name)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 14)
    c.drawCentredString(cx, height - 110 * mm, "has successfully completed")
    title = cert.course_title
    size = _fit(c, title, "Helvetica-Bold", 22, width - 80 * mm)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, height - 124 * mm, title)

    details = [f"Issued {cert.issued_at:%d %B %Y} (UTC)"]
    if cert.cpd_hours:
        details.append(f"{cert.cpd_hours} CPD hours")
    if cert.instructor_names:
        details.append(f"Instructor: {cert.instructor_names[:120]}")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(cx, height - 138 * mm, "   ·   ".join(details))

    if template and template.signatory_name:
        c.setStrokeColor(MUTED)
        c.line(40 * mm, 42 * mm, 110 * mm, 42 * mm)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40 * mm, 36 * mm, template.signatory_name[:60])
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(40 * mm, 31 * mm, template.signatory_title[:60])

    url = f"{settings.FRONTEND_URL}/verify/{cert.verification_code}"
    widget = qr.QrCodeWidget(url)
    x0, y0, x1, y1 = widget.getBounds()
    box = 30 * mm
    d = Drawing(box, box, transform=[box / (x1 - x0), 0, 0, box / (y1 - y0), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, width - 58 * mm, 26 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(width - 22 * mm, 22 * mm, f"Verify: {cert.verification_code}")

    c.showPage()
    c.save()
    return buf.getvalue()
