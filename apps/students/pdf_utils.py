# students/pdf_utils.py
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
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