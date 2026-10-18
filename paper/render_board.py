# -*- coding: utf-8 -*-
"""
The Right-to-Repair Board Rescuer Deck -> one-page two-column PDF.

Formatting reproduced from the original render_board.py:
  Letter page, Times (Nimbus Roman) TTFs, justified body with en_GB hyphenation,
  54 pt margins, 16 pt gutter, rule / author grid / rule / Abstract header,
  "Attention is All You Need" layout.
Text is the original paper's text (hyphenation from the source PDF repaired).
"""
import re, os
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, FrameBreak, NextPageTemplate, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

HERE = os.path.dirname(os.path.abspath(__file__))
FONTDIRS = [os.path.join(HERE, "fonts"), "/tmp/replay/fonts", "/usr/share/fonts/noto"]

def fontfile(name):
    for d in FONTDIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise SystemExit("missing font " + name)

pdfmetrics.registerFont(TTFont('Nimbus',    fontfile('NimbusRoman-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-B',  fontfile('NimbusRoman-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-I',  fontfile('NimbusRoman-Italic.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-BI', fontfile('NimbusRoman-BoldItalic.ttf')))
pdfmetrics.registerFontFamily('Nimbus', normal='Nimbus', bold='Nimbus-B',
                              italic='Nimbus-I', boldItalic='Nimbus-BI')
pdfmetrics.registerFont(TTFont('NotoSans', fontfile('NotoSans-Regular.ttf')))   # rupee glyph

def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def markup(t):
    t = esc(t)
    t = t.replace('\u20b9', '<font name="NotoSans">\u20b9</font>')
    t = re.sub(r'\s+', ' ', t)
    t = t.replace(' .', '.').replace(' ,', ',').replace(' )', ')').replace('( ', '(')
    return t.strip()

# ------------------------------------------------------------------ styles
BODY = ParagraphStyle('body', fontName='Nimbus', fontSize=10, leading=11.3, alignment=TA_JUSTIFY,
                      hyphenationLang='en_GB', spaceShrinkage=0.08, spaceAfter=0.6)
H1 = ParagraphStyle('h1', fontName='Nimbus-B', fontSize=11.5, leading=13.2,
                    spaceBefore=7, spaceAfter=2, keepWithNext=1)
TITLE = ParagraphStyle('title', fontName='Nimbus-B', fontSize=16.5, leading=19.5,
                       alignment=TA_CENTER, spaceAfter=4)
AUTHCELL = ParagraphStyle('ac', fontName='Nimbus', fontSize=8.8, leading=10.4, alignment=TA_CENTER)
AFF = ParagraphStyle('aff', fontName='Nimbus', fontSize=9.8, leading=11.6,
                     alignment=TA_CENTER, spaceAfter=1)
ABSHEAD = ParagraphStyle('ah', fontName='Nimbus-B', fontSize=11.5, leading=13.5,
                         alignment=TA_CENTER, spaceBefore=1, spaceAfter=4)
ABS = ParagraphStyle('abs', fontName='Nimbus', fontSize=9.6, leading=11.4, alignment=TA_JUSTIFY,
                     hyphenationLang='en_GB', spaceShrinkage=0.08)

PW, PH = letter
TEXTW = PW - 108.0
LM = RM = TM = BM = 54.0
GUT = 16.0
COLW = (TEXTW - GUT) / 2.0

def footer(c, doc):
    c.saveState(); c.setFont('Nimbus', 9)
    c.drawCentredString(PW / 2.0, 30, str(doc.page)); c.restoreState()

# ------------------------------------------------------------------ content
TITLE_TXT = 'The Right-to-Repair Board Rescuer Deck'

AUTHORS = [
    ("Johnsteven R",      "johnsteven.r2026@vitstudent.ac.in"),
    ("Pranav Charan B",   "pranavcharan.b2026@vitstudent.ac.in"),
    ("S Raaghav Ayyavoo", "raaghavayyavoo.s2026@vitstudent.ac.in"),
    ("Maarthi P",         "maarthi.p2026@vitstudent.ac.in"),
    ("N Akilan Gautham",  "akilangautham.n2026@vitstudent.ac.in"),
    ("M Dharshan Bagath", "dharshanbagath.m2026@vitstudent.ac.in"),
    ("T D Asvin",         "asvin.td2026@vitstudent.ac.in"),
]
AFFIL = 'Vellore Institute of Technology, Chennai, Tamil Nadu, India'

ABSTRACT = (
 "Electronic control boards in modern appliances and vehicles are routinely declared unrepairable: "
 "a single short-circuited power semiconductor worth a few tens of rupees leads a technician to "
 "recommend replacing an entire motherboard costing thousands. This paper presents the Right-to-Repair "
 "Board Rescuer Deck, a portable diagnostic platform aimed at neighbourhood repair shops "
 "(repair-walas) and DIY consumers. The key insight is that failed power semiconductors expose "
 "themselves through localised thermal and electrical signatures when the board is energised at a "
 "safe, low voltage. The deck combines a low-cost thermal-imaging array (MLX90640) with automated "
 "multimeter probes in a testing tray, and uses edge AI to localise the faulty device, identify its "
 "part number, retrieve a datasheet, and display a step-by-step desoldering and replacement guide. "
 "The approach reduces repair cost from whole-board replacement to component-level substitution, "
 "extending device lifetime and cutting electronic waste."
)

SECTIONS = [
 ('1.&nbsp;&nbsp;The Average Person\u2019s Problem', [
  "When a washing machine, a modern microwave, or a car dashboard breaks, the local repairman usually "
  "says, \u201cThe whole motherboard is dead, you need to buy a new one for \u20b915,000.\u201d In reality, a "
  "single \u20b950 power semiconductor (such as a MOSFET or a voltage regulator) has short-circuited. "
  "Manufacturers use proprietary software to lock down diagnostics, forcing consumers into expensive "
  "replacements.",
  "The gap between the cost of the failed part and the price of the repair is the core economic problem. "
  "A transistor or regulator costs between \u20b910 and \u20b9100, yet a board replacement for a washing "
  "machine or dashboard can be quoted at \u20b98,000 to \u20b920,000. Because the board is sealed or "
  "undocumented, the technician cannot cheaply prove that the fault is localised, so serviceable "
  "hardware becomes electronic waste. Manufacturers reinforce this with proprietary diagnostics, "
  "serialised parts, and software locks that reject replacements.",
 ]),
 ('2.&nbsp;&nbsp;The Semiconductor Connection', [
  "Modern appliance boards are packed with microcontrollers and power semiconductors. When they fail, "
  "they usually fail \u201cshort\u201d or \u201copen\u201d, creating a detectable thermal or electrical signature.",
  "Power semiconductors fail most often because they carry the largest currents and dissipate the most "
  "heat. A MOSFET switching a motor can fail as a drain-to-source short, while a regulator or rectifier "
  "can fail short, open, or drift out of specification after mains transients, inrush current, thermal "
  "cycling, moisture, or ageing. A shorted device draws abnormal current and becomes a localised hot "
  "spot within seconds, whereas an open device removes current from a whole rail, so a safe, "
  "current-limited low voltage can reveal either fault.",
 ]),
 ('3.&nbsp;&nbsp;The Proposed Solution', [
  "We propose a portable Right-to-Repair Board Rescuer Deck designed for local neighbourhood repair "
  "shops (repair-walas) and DIY consumers.",
  "The deck is a portable, laptop-like instrument. Its lid houses a low-cost thermal array (the "
  "MLX90640, 32 by 24 pixels) and a camera for part-number recognition; its base holds a testing tray, "
  "retractable multimeter probes, and a current-limited power supply. A single-board computer and "
  "touchscreen run the diagnosis locally, and the unit is built from widely available parts so that it "
  "stays affordable and works offline.",
 ]),
 ('4.&nbsp;&nbsp;How It Works', [
  "The deck has a built-in thermal imaging camera (such as an MLX90640 sensor) and automated multimeter "
  "probes built into a testing tray. The user places the broken appliance motherboard on the deck, and "
  "the deck injects a safe, low voltage into the board. The thermal camera instantly spots the exact "
  "semiconductor that is overheating (the shorted chip). The deck\u2019s screen then uses edge AI to "
  "identify the chip\u2019s part number, searches for a datasheet, and shows a 3D video guide on how to "
  "desolder and replace that exact \u20b950 chip.",
  "In use, the operator places the suspect board on the tray, where spring-loaded probes contact its "
  "main power rails, and the deck energises it at a safe, current-limited voltage while capturing a "
  "thermal image. A Python and OpenCV pipeline compares the frame with the ambient baseline, flags "
  "regions that exceed a temperature threshold, and overlays their coordinates. The hottest anomaly is "
  "almost always the shorted device, because that is where electrical energy becomes heat. The deck "
  "then reads the part number, retrieves its datasheet, and shows a three-dimensional guide for "
  "replacing it.",
 ]),
]

# ------------------------------------------------------------------ header
def author_grid():
    cells = [Paragraph('<b>%s</b><br/>%s' % (n, e), AUTHCELL) for n, e in AUTHORS]
    pos = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 1)]   # last author centred
    grid = [[Paragraph('', AUTHCELL) for _ in range(3)] for _ in range(3)]
    for (r, c), cell in zip(pos, cells):
        grid[r][c] = cell
    t = Table(grid, colWidths=[TEXTW / 3.0] * 3, hAlign='CENTER')
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 3),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                           ('TOPPADDING', (0, 0), (-1, -1), 1),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    return t

def rule(sb, sa):
    return HRFlowable(width='100%', thickness=0.6, color=colors.HexColor('#666666'),
                      spaceBefore=sb, spaceAfter=sa, lineCap='butt')

header = [Paragraph(markup(TITLE_TXT), TITLE),
          rule(16, 7),
          author_grid(),
          Paragraph(AFFIL, AFF),
          rule(5, 17),
          Paragraph('Abstract', ABSHEAD),
          Paragraph(markup(ABSTRACT), ABS)]
def flowheight(fs):        # wrap() ignores spaceBefore/spaceAfter -> include them
    h = 0.0
    for f in fs:
        h += getattr(f, 'spaceBefore', 0) or 0
        h += f.wrap(TEXTW, 10000)[1]
        h += getattr(f, 'spaceAfter', 0) or 0
    return h

HDRH = flowheight(header) + 26          # header block, no overflow into the columns
HDRGAP = (295.4 - HDRH) / 2.0           # places section 1 at the reference y (351.8)
TOPH = HDRH + HDRGAP

ft = Frame(LM, PH - TM - TOPH, TEXTW, TOPH, id='top',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fl = Frame(LM, BM, COLW, PH - TM - TOPH - HDRGAP - BM, id='l',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fr = Frame(LM + COLW + GUT, BM, COLW, PH - TM - TOPH - HDRGAP - BM, id='r',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fl2 = Frame(LM, BM, COLW, PH - TM - BM, id='l2',
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fr2 = Frame(LM + COLW + GUT, BM, COLW, PH - TM - BM, id='r2',
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

OUT = os.path.join(HERE, 'Right-to-Repair_Board_Rescuer_Deck.pdf')
doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=LM, rightMargin=RM,
                      topMargin=TM, bottomMargin=BM, title=TITLE_TXT,
                      author=', '.join(a[0] for a in AUTHORS))
doc.addPageTemplates([PageTemplate(id='first', frames=[ft, fl, fr], onPage=footer),
                      PageTemplate(id='later', frames=[fl2, fr2], onPage=footer)])
story = [NextPageTemplate('later')] + header + [FrameBreak()]
for h, paras in SECTIONS:
    story.append(Paragraph(h, H1))
    for p in paras:
        story.append(Paragraph(markup(p), BODY))
doc.build(story)
print('built', OUT, ' header %.1f pt' % HDRH)
