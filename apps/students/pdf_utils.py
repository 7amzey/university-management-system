# students/pdf_utils.py
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable, Image
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os

# register an Arabic font — download Amiri or use any Arabic TTF you have
# place the font file in your project's static/fonts/ directory
FONT_PATH = r'C:\Users\Hamze Younis\Desktop\StudentPortal_V2\university_management_system\static\fonts\Amiri-Regular.ttf'
pdfmetrics.registerFont(TTFont('Amiri', FONT_PATH))
def ar(text):
    """Reshape and reorder Arabic text for correct RTL rendering."""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def ar_style(size=11, bold=False):
    font = 'Amiri'
    return ParagraphStyle(
        name='Arabic',
        fontName=font,
        fontSize=size,
        leading=size + 6,
        alignment=2,  # right align
    )

LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')

def pdf_header(story, info_lines):
    """
    Renders: centered logo → university name → HR → student info lines.
    info_lines: list of plain Arabic strings e.g. ['الرقم: 123', 'التخصص: IT']
    """
    # Logo centered
    logo = Image(LOGO_PATH, width=2*cm, height=2*cm)
    logo.hAlign = 'CENTER'
    story.append(logo)
    story.append(Spacer(1, 6))

    # University name centered
    centered = ParagraphStyle(
        name='ArabicCenter',
        fontName='Amiri',
        fontSize=16,
        leading=22,
        alignment=1,  # center
    )
    story.append(Paragraph(ar('جامعة البلقاء التطبيقية'), centered))
    story.append(Spacer(1, 8))

    # Horizontal rule
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#119F61')))
    story.append(Spacer(1, 8))

    # Student info lines right-aligned
    for line in info_lines:
        story.append(Paragraph(ar(line), ar_style(size=11)))
    story.append(Spacer(1, 16))