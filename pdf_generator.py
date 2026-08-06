import os
import csv
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_pdf_report(csv_path: str, pdf_output_path: str = None) -> str:
    """Generate a clean, professional PDF report from an attendance CSV log."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    filename = os.path.basename(csv_path)
    if pdf_output_path is None:
        pdf_name = filename.replace(".csv", ".pdf")
        pdf_output_path = os.path.join(os.path.dirname(csv_path), pdf_name)

    # Read CSV data
    df = pd.read_csv(csv_path)

    # Setup ReportLab Document
    doc = SimpleDocTemplate(
        pdf_output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []

    styles = getSampleStyleSheet()

    # Custom Color Palette (Gold / Amber Theme)
    GOLD_DARK = colors.HexColor("#78350f")
    GOLD_PRIMARY = colors.HexColor("#d97706")
    GOLD_LIGHT = colors.HexColor("#fef3c7")
    TEXT_DARK = colors.HexColor("#1c1917")
    TEXT_MUTED = colors.HexColor("#78716c")

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=GOLD_DARK,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=TEXT_MUTED,
        spaceAfter=15,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=TEXT_DARK,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXT_DARK,
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.white,
    )

    # Document Header
    story.append(Paragraph("VisionTrack AI — Official Attendance Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M:%S')} • Source: {filename}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD_PRIMARY, spaceAfter=15))

    # Summary Stats Box Table
    summary_data = [
        [
            Paragraph(f"<b>Report Log:</b> {filename}", meta_style),
            Paragraph(f"<b>Total Present:</b> {len(df)} person(s)", meta_style),
            Paragraph(f"<b>Export Time:</b> {datetime.now().strftime('%H:%M:%S')}", meta_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[200, 180, 160])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GOLD_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, GOLD_PRIMARY),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 18))

    # Data Table Section Header
    story.append(Paragraph("Attendance Records", ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, leading=16, textColor=GOLD_DARK, spaceAfter=8)))

    # Main Attendance Data Table
    table_data = [
        [
            Paragraph("Person Name", header_cell_style),
            Paragraph("Status", header_cell_style),
            Paragraph("Timestamp", header_cell_style),
            Paragraph("Video Time", header_cell_style),
            Paragraph("Frame #", header_cell_style),
        ]
    ]

    for _, row in df.iterrows():
        name = str(row.get("Name", "N/A"))
        status = str(row.get("Status", "Present"))
        ts = str(row.get("Timestamp", "N/A"))
        v_time = str(row.get("Video Time", "N/A"))
        frame = str(row.get("Frame", "N/A"))

        table_data.append([
            Paragraph(name, cell_style),
            Paragraph(f"<font color='#d97706'><b>{status}</b></font>", cell_style),
            Paragraph(ts, cell_style),
            Paragraph(v_time, cell_style),
            Paragraph(frame, cell_style),
        ])

    data_table = Table(table_data, colWidths=[130, 90, 150, 90, 80])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), GOLD_PRIMARY),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GOLD_LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e7e5e4")),
    ]))

    story.append(data_table)

    # Footer Spacer & Notice
    story.append(Spacer(1, 25))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db"), spaceAfter=8))
    footer_text = f"Report generated automatically by VisionTrack AI Platform. Confidential document."
    story.append(Paragraph(footer_text, ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=TEXT_MUTED, alignment=1)))

    doc.build(story)
    return pdf_output_path

if __name__ == "__main__":
    test_csv = "attendance_logs/video_attendance_report.csv"
    if os.path.exists(test_csv):
        pdf = generate_pdf_report(test_csv)
        print(f"[INFO] Generated Test PDF: {pdf}")
