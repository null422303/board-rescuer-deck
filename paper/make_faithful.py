#!/usr/bin/env python3
"""
Right-to-Repair Board Rescuer Deck -> faithful one-page, two-column PDF.

Content is the ORIGINAL text (verbatim, only fixing PDF hyphenation).
Layout follows "Attention is All You Need": serif, two columns,
rule / author grid (John first) / rule / Abstract / body.
"""
import math, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, HRFlowable)
from reportlab.lib.colors import HexColor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "Right-to-Repair_Board_Rescuer_Deck.pdf")
NF = "/usr/share/fonts/noto"
for name, fn in (("NS", "NotoSerif-Regular.ttf"), ("NS-B", "NotoSerif-Bold.ttf"),
                 ("NS-I", "NotoSerif-Italic.ttf"), ("NS-BI", "NotoSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(name, f"{NF}/{fn}"))
pdfmetrics.registerFontFamily("NS", normal="NS", bold="NS-B", italic="NS-I", boldItalic="NS-BI")

INK  = HexColor("#000000")
RULE = HexColor("#5a5a5a")

TITLE = "The Right-to-Repair Board Rescuer Deck"

AUTHORS = [
    ("Johnsteven R",       "johnsteven.r2026@vitstudent.ac.in"),
    ("Pranav Charan B",    "pranavcharan.b2026@vitstudent.ac.in"),
    ("S Raaghav Ayyavoo",  "raaghavayyavoo.s2026@vitstudent.ac.in"),
    ("Maarthi P",          "maarthi.p2026@vitstudent.ac.in"),
    ("N Akilan Gautham",   "akilangautham.n2026@vitstudent.ac.in"),
    ("M Dharshan Bagath",  "dharshanbagath.m2026@vitstudent.ac.in"),
    ("T D Asvin",          "asvin.td2026@vitstudent.ac.in"),
]
AFFIL = "Vellore Institute of Technology, Chennai, Tamil Nadu, India"

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

BODY = [
 ("1.  The Average Person\u2019s Problem", [
  "When a washing machine, a modern microwave, or a car dashboard breaks, the local repairman usually "
  "says, \u201cThe whole motherboard is dead, you need to buy a new one for \u20b915,000.\u201d In reality, a single "
  "\u20b950 power semiconductor (such as a MOSFET or a voltage regulator) has short-circuited. "
  "Manufacturers use proprietary software to lock down diagnostics, forcing consumers into expensive "
  "replacements.",
  "The gap between the cost of the failed part and the price of the repair is the core economic "
  "problem. A transistor or regulator costs between \u20b910 and \u20b9100, yet a board replacement for a "
  "washing machine or dashboard can be quoted at \u20b98,000 to \u20b920,000. Because the board is sealed or "
  "undocumented, the technician cannot cheaply prove that the fault is localised, so serviceable "
  "hardware becomes electronic waste. Manufacturers reinforce this with proprietary diagnostics, "
  "serialised parts, and software locks that reject replacements.",
 ]),
 ("2.  The Semiconductor Connection", [
  "Modern appliance boards are packed with microcontrollers and power semiconductors. When they fail, "
  "they usually fail \u201cshort\u201d or \u201copen\u201d, creating a detectable thermal or electrical signature.",
  "Power semiconductors fail most often because they carry the largest currents and dissipate the "
  "most heat. A MOSFET switching a motor can fail as a drain-to-source short, while a regulator or "
  "rectifier can fail short, open, or drift out of specification after mains transients, inrush "
  "current, thermal cycling, moisture, or ageing. A shorted device draws abnormal current and becomes "
  "a localised hot spot within seconds, whereas an open device removes current from a whole rail, so a "
  "safe, current-limited low voltage can reveal either fault.",
 ]),
 ("3.  The Proposed Solution", [
  "We propose a portable Right-to-Repair Board Rescuer Deck designed for local neighbourhood repair "
  "shops (repair-walas) and DIY consumers.",
  "The deck is a portable, laptop-like instrument. Its lid houses a low-cost thermal array (the "
  "MLX90640, 32 by 24 pixels) and a camera for part-number recognition; its base holds a testing "
  "tray, retractable multimeter probes, and a current-limited power supply. A single-board computer "
  "and touchscreen run the diagnosis locally, and the unit is built from widely available parts so "
  "that it stays affordable and works offline.",
 ]),
 ("4.  How It Works", [
  "The deck has a built-in thermal imaging camera (such as an MLX90640 sensor) and automated "
  "multimeter probes built into a testing tray. The user places the broken appliance motherboard on "
  "the deck, and the deck injects a safe, low voltage into the board. The thermal camera instantly "
  "spots the exact semiconductor that is overheating (the shorted chip). The deck\u2019s screen then uses "
  "edge AI to identify the chip\u2019s part number, searches for a datasheet, and shows a 3D video guide "
  "on how to desolder and replace that exact \u20b950 chip.",
  "In use, the operator places the suspect board on the tray, where spring-loaded probes contact its "
  "main power rails, and the deck energises it at a safe, current-limited voltage while capturing a "
  "thermal image. A Python and OpenCV pipeline compares the frame with the ambient baseline, flags "
  "regions that exceed a temperature threshold, and overlays their coordinates. The hottest anomaly "
  "is almost always the shorted device, because that is where electrical energy becomes heat. The "
  "deck then reads the part number, retrieves its datasheet, and shows a three-dimensional guide for "
  "replacing it.",
 ]),
]

PW, PH = A4
M      = 13 * mm
GUT    = 6 * mm
COLW   = (PW - 2 * M - GUT) / 2.0
FS     = 8.8          # body size
LEAD   = 11.0

# ---------------------------------------------------------------- header metrics
TITLE_FS, TITLE_LEAD = 16.5, 19
AUTH_FS, MAIL_FS, AUTH_ROW = 9.2, 7.5, 25
ABS_FS = 8.7
ABS_LEAD = 11.2
ABS_W  = (PW - 2 * M) * 0.78
ABS_X  = (PW - ABS_W) / 2.0

def header_bottom():
    y = PH - M
    y -= TITLE_LEAD + 7
    y -= 12                                    # gap to rule
    y -= 13                                    # after rule
    rows = math.ceil(len(AUTHORS) / 3)
    y -= rows * AUTH_ROW
    y -= 4
    y -= 13                                    # affiliation
    y -= 9
    y -= 8                                     # gap after rule
    y -= 13                                    # "Abstract" heading
    nlines = len(simpleSplit(ABSTRACT, "NS", ABS_FS, ABS_W))
    y -= nlines * ABS_LEAD
    return y - 12

HDR_BOT = header_bottom()

def draw_header(c, doc):
    c.saveState()
    y = PH - M
    c.setFillColor(INK); c.setStrokeColor(RULE)

    c.setFont("NS-B", TITLE_FS)
    c.drawCentredString(PW / 2, y - TITLE_LEAD + 4, TITLE)
    y -= TITLE_LEAD + 7

    c.setLineWidth(0.7); c.line(M, y, PW - M, y)
    y -= 13

    colw = (PW - 2 * M) / 3.0
    for i, (nm, em) in enumerate(AUTHORS):
        r, cc = divmod(i, 3)
        x = M + cc * colw + colw / 2.0
        yy = y - r * AUTH_ROW
        c.setFont("NS-B", AUTH_FS); c.drawCentredString(x, yy, nm)
        c.setFont("NS", MAIL_FS);   c.drawCentredString(x, yy - 11, em)
    rows = math.ceil(len(AUTHORS) / 3)
    y -= rows * AUTH_ROW
    y -= 4

    c.setFont("NS-I", 9.0); c.drawCentredString(PW / 2, y, AFFIL)
    y -= 13

    c.setLineWidth(0.7); c.line(M, y, PW - M, y)
    y -= 8
    y -= 13

    c.setFont("NS-B", 10.5); c.drawCentredString(PW / 2, y, "Abstract")
    y -= 13

    c.setFont("NS", ABS_FS)
    for line in simpleSplit(ABSTRACT, "NS", ABS_FS, ABS_W):
        c.drawString(ABS_X, y, line)
        y -= ABS_LEAD
    c.restoreState()

def draw_furniture(c, doc):
    c.saveState(); c.setFont("NS", 8); c.setFillColor(RULE)
    c.drawCentredString(PW / 2, 8 * mm, str(c.getPageNumber()))
    c.restoreState()

class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=A4, leftMargin=M, rightMargin=M,
                         topMargin=M, bottomMargin=11 * mm,
                         title=TITLE, author=", ".join(a[0] for a in AUTHORS),
                         subject="Right to repair, electronics diagnostics")
        top = HDR_BOT - 10
        h1 = top - 12 * mm
        first_l = Frame(M, 11 * mm, COLW, h1, id="l1",
                        leftPadding=0, rightPadding=4, topPadding=0, bottomPadding=0)
        first_r = Frame(M + COLW + GUT, 11 * mm, COLW, h1, id="r1",
                        leftPadding=4, rightPadding=0, topPadding=0, bottomPadding=0)
        l2 = Frame(M, 11 * mm, COLW, PH - M - 11 * mm, id="l2",
                   leftPadding=0, rightPadding=4, topPadding=0, bottomPadding=0)
        r2 = Frame(M + COLW + GUT, 11 * mm, COLW, PH - M - 11 * mm, id="r2",
                   leftPadding=4, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="first", frames=[first_l, first_r], onPage=self._p),
            PageTemplate(id="rest",  frames=[l2, r2], onPage=self._p),
        ])
    def _p(self, c, doc):
        if c.getPageNumber() == 1:
            draw_header(c, doc)
        draw_furniture(c, doc)

BH  = ParagraphStyle("bh", fontName="NS-B", fontSize=10.2, leading=12.6,
                     textColor=INK, spaceBefore=4.6, spaceAfter=3.0, alignment=0)
BP  = ParagraphStyle("bp", fontName="NS", fontSize=FS, leading=LEAD,
                     textColor=INK, alignment=TA_JUSTIFY, spaceAfter=4.2)

story = []
for head, paras in BODY:
    story.append(Paragraph(head, BH))
    for p in paras:
        story.append(Paragraph(p, BP))

Doc(OUT).build(story)
print("wrote", OUT)
