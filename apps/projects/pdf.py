import os

from fpdf import FPDF, XPos, YPos
from fpdf.fonts import FontFace

# The app's accent teal (--accent in static/css/app.css), reused here so an
# exported talk looks like it came from the same product.
_ACCENT_RGB = (22, 120, 159)


class _ToolboxTalkPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "Cleantech1 -- Toolbox Talk (TBT)", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "Cleantech1 Pty Ltd -- Daily Supervisor Checklist", align="C")


def _field_row(pdf, label, value):
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(38, 7, label)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, value or "--", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_toolbox_talk_pdf(talk) -> bytes:
    """Renders a ToolboxTalk as an A4 document matching the paper TBT form
    this replaces: title, date/location/supervisor fields, the briefing
    itself (as authored in the rich text editor), and a sign-off table --
    same shape as the physical form, so it's a drop-in replacement for it."""
    pdf = _ToolboxTalkPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    location = "General (not tied to a project)"
    if talk.project:
        location = talk.project.location or talk.project.name
    supervisor = talk.conducted_by.get_full_name() or talk.conducted_by.username

    _field_row(pdf, "Date:", talk.work_date.strftime("%d/%m/%Y"))
    _field_row(pdf, "Location:", location)
    _field_row(pdf, "Supervisor Name:", supervisor)

    pdf.ln(2)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 8, talk.topic)
    pdf.ln(2)

    if talk.content:
        pdf.set_font("Helvetica", "", 11)
        # A plain "-" bullet, not the default "disc" -- the core Helvetica
        # font (no embedded TTF) can't render the Unicode bullet glyph.
        # font_family matches the rest of the doc (write_html defaults to
        # Times otherwise); heading color matches the app's own accent.
        pdf.write_html(
            talk.content, ul_bullet_char="-", font_family="helvetica",
            tag_styles={
                "h3": FontFace(color=_ACCENT_RGB, size_pt=13),
                "h4": FontFace(color=_ACCENT_RGB, size_pt=12),
            },
        )
        pdf.ln(4)

    attendees = list(talk.attendees.select_related("employee").order_by("employee__first_name", "employee__last_name"))
    if attendees:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Attendees", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
        with pdf.table(col_widths=(45, 25, 20, 40), text_align=("LEFT", "LEFT", "CENTER", "CENTER")) as table:
            header = table.row()
            for h in ("Name", "Phone", "Signed", "Signature"):
                header.cell(h)
            for a in attendees:
                row = table.row()
                row.cell(a.employee.full_name)
                row.cell(a.employee.phone or "--")
                row.cell(a.signed_at.strftime("%d/%m/%y %H:%M") if a.signed_at else "Not signed")
                if a.signature and a.signature.name and os.path.exists(a.signature.path):
                    row.cell("", img=a.signature.path, img_fill_width=True)
                else:
                    row.cell("--")

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(
        0, 5,
        "By signing this document, each attendee confirms they have read and understood the contents of "
        "this Toolbox Talk and agree to comply with all safety requirements and procedures.",
    )

    return bytes(pdf.output())
