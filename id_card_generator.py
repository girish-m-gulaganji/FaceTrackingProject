import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.barcode import qr

def generate_id_card(person_name: str, department: str = "AI Engineering", role: str = "Member", enrolled_date: str = "2026-08-10"):
    """Generate printable official Smart ID Card PDF for an enrolled person in Deep Blue theme."""
    os.makedirs("attendance_logs", exist_ok=True)
    filename = f"ID_Card_{person_name.replace(' ', '_')}.pdf"
    filepath = os.path.join("attendance_logs", filename)

    c = canvas.Canvas(filepath, pagesize=(3.5 * inch, 2.25 * inch))

    # Background Card Frame (Sleek Dark Slate Blue)
    c.setFillColor(HexColor("#0F172A"))
    c.rect(0, 0, 3.5 * inch, 2.25 * inch, fill=1, stroke=0)

    # Top Primary Header Accent (Deep Royal Blue)
    c.setFillColor(HexColor("#1E3A5F"))
    c.rect(0, 1.95 * inch, 3.5 * inch, 0.30 * inch, fill=1, stroke=0)

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(0.15 * inch, 2.05 * inch, "VISIONTRACK AI — SMART ID BADGE")

    # Person Name & Details
    c.setFillColor(HexColor("#60A5FA"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.20 * inch, 1.65 * inch, person_name.upper())

    c.setFillColor(HexColor("#E2E8F0"))
    c.setFont("Helvetica", 9)
    c.drawString(0.20 * inch, 1.40 * inch, f"Dept: {department}")
    c.drawString(0.20 * inch, 1.20 * inch, f"Role: {role}")
    c.drawString(0.20 * inch, 1.00 * inch, f"Enrolled: {enrolled_date}")

    c.setFillColor(HexColor("#38BDF8"))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(0.20 * inch, 0.65 * inch, "VERIFIED 512-D ARCFACE EMBEDDING")

    # QR Code Verification
    qr_code = qr.QrCodeWidget(f"VISIONTRACK_ID:{person_name}:{department}")
    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    d = Drawing(45, 45, transform=[45.0/width, 0, 0, 45.0/height, 0, 0])
    d.add(qr_code)
    d.drawOn(c, 2.70 * inch, 0.65 * inch)

    # Bottom Footer (Accent Line & Fine Print)
    c.setFillColor(HexColor("#2563EB"))
    c.rect(0, 0, 3.5 * inch, 0.15 * inch, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 6)
    c.drawString(0.15 * inch, 0.04 * inch, "OFFICIAL IDENTIFICATION BADGE — AUTHORIZED ACCESS ONLY")

    c.save()
    return filepath

if __name__ == "__main__":
    path = generate_id_card("Girish M", "AI Engineering", "Lead Developer")
    print(f"[INFO] Generated ID Card PDF: {path}")
