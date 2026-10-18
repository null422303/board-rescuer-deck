# -*- coding: utf-8 -*-
"""
Long-form version of the Board Rescuer Deck paper.

Page 1 uses EXACTLY the reference theme: Letter, Nimbus Roman, two columns,
title / rule / author grid / affiliation / rule / Abstract, justified with
en_GB hyphenation.  Sections 1-4 are the reference text; the remaining
sections add the built prototype, measurements and figures.
"""
import os, re
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, FrameBreak, NextPageTemplate, Table, TableStyle,
                                KeepTogether, Image)
from reportlab.platypus.flowables import HRFlowable
from PIL import Image as PILImage

HERE = os.path.dirname(os.path.abspath(__file__))
FIGD = os.path.join(HERE, "figures")
PHOD = os.path.join(HERE, "photos")
FONTDIRS = [os.path.join(HERE, "fonts"), "/tmp/replay/fonts"]

def fontfile(n):
    for d in FONTDIRS:
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    raise SystemExit("missing font " + n)

pdfmetrics.registerFont(TTFont('Nimbus',    fontfile('NimbusRoman-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-B',  fontfile('NimbusRoman-Bold.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-I',  fontfile('NimbusRoman-Italic.ttf')))
pdfmetrics.registerFont(TTFont('Nimbus-BI', fontfile('NimbusRoman-BoldItalic.ttf')))
pdfmetrics.registerFontFamily('Nimbus', normal='Nimbus', bold='Nimbus-B',
                              italic='Nimbus-I', boldItalic='Nimbus-BI')
pdfmetrics.registerFont(TTFont('NotoSans', fontfile('NotoSans-Regular.ttf')))

def mk(t):
    t = t.replace('&#8377;', '\u20b9').replace('\u20b9', '<font name="NotoSans">\u20b9</font>')
    return t

# ------------------------------------------------------------------ styles (reference theme)
BODY = ParagraphStyle('body', fontName='Nimbus', fontSize=10, leading=11.6, alignment=TA_JUSTIFY,
                      hyphenationLang='en_GB', spaceShrinkage=0.08, spaceAfter=1.0)
H1 = ParagraphStyle('h1', fontName='Nimbus-B', fontSize=11.5, leading=13.2,
                    spaceBefore=8, spaceAfter=3, keepWithNext=1)
H2 = ParagraphStyle('h2', fontName='Nimbus-B', fontSize=10, leading=12,
                    spaceBefore=6, spaceAfter=1.5, keepWithNext=1)
TITLE = ParagraphStyle('title', fontName='Nimbus-B', fontSize=16.5, leading=19.5,
                       alignment=TA_CENTER, spaceAfter=4)
AUTHCELL = ParagraphStyle('ac', fontName='Nimbus', fontSize=8.8, leading=10.4, alignment=TA_CENTER)
AFF = ParagraphStyle('aff', fontName='Nimbus', fontSize=9.8, leading=11.6,
                     alignment=TA_CENTER, spaceAfter=1)
ABSHEAD = ParagraphStyle('ah', fontName='Nimbus-B', fontSize=11.5, leading=13.5,
                         alignment=TA_CENTER, spaceBefore=1, spaceAfter=4)
ABS = ParagraphStyle('abs', fontName='Nimbus', fontSize=9.6, leading=11.4, alignment=TA_JUSTIFY,
                     hyphenationLang='en_GB', spaceShrinkage=0.08)
CAP = ParagraphStyle('cap', fontName='Nimbus', fontSize=8.2, leading=11.6, alignment=TA_JUSTIFY,
                     spaceBefore=2, spaceAfter=7)
REF = ParagraphStyle('ref', fontName='Nimbus', fontSize=8.2, leading=11.6, alignment=TA_LEFT,
                     spaceAfter=0.0, leftIndent=9, firstLineIndent=-9)
BUL = ParagraphStyle('bul', fontName='Nimbus', fontSize=10, leading=11.6, alignment=TA_JUSTIFY,
                     leftIndent=9, bulletIndent=0, spaceAfter=2,
                     hyphenationLang='en_GB', spaceShrinkage=0.08)

PW, PH = letter
TEXTW = PW - 108.0
LM = RM = TM = BM = 54.0
GUT = 16.0
COLW = (TEXTW - GUT) / 2.0

def footer(c, doc):
    c.saveState(); c.setFont('Nimbus', 9)
    c.drawCentredString(PW / 2.0, 30, str(doc.page)); c.restoreState()

# ------------------------------------------------------------------ reference content
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

# sections 1-4 = the reference text, verbatim
REF_SECTIONS = [
 ('1.&nbsp;&nbsp;The Average Person\u2019s Problem', [
  "When a washing machine, a modern microwave, or a car dashboard breaks, the local repairman usually "
  "says, \u201cThe whole motherboard is dead, you need to buy a new one for &#8377;15,000.\u201d In reality, a "
  "single &#8377;50 power semiconductor (such as a MOSFET or a voltage regulator) has short-circuited. "
  "Manufacturers use proprietary software to lock down diagnostics, forcing consumers into expensive "
  "replacements.",
  "The gap between the cost of the failed part and the price of the repair is the core economic problem. "
  "A transistor or regulator costs between &#8377;10 and &#8377;100, yet a board replacement for a washing "
  "machine or dashboard can be quoted at &#8377;8,000 to &#8377;20,000. Because the board is sealed or "
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
  "desolder and replace that exact &#8377;50 chip.",
  "In use, the operator places the suspect board on the tray, where spring-loaded probes contact its "
  "main power rails, and the deck energises it at a safe, current-limited voltage while capturing a "
  "thermal image. A Python and OpenCV pipeline compares the frame with the ambient baseline, flags "
  "regions that exceed a temperature threshold, and overlays their coordinates. The hottest anomaly is "
  "almost always the shorted device, because that is where electrical energy becomes heat. The deck "
  "then reads the part number, retrieves its datasheet, and shows a three-dimensional guide for "
  "replacing it.",
 ]),
]

# ------------------------------------------------------------------ figures (column width)
def fig(name, caption, w=COLW, photo=False):
    p = os.path.join(PHOD if photo else FIGD, name)
    iw, ih = PILImage.open(p).size
    im = Image(p, width=w, height=w * ih / iw)
    return KeepTogether([im, Paragraph(mk(caption), CAP)])

def table(rows, widths, caption, head=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
    st = [("FONT", (0, 0), (-1, -1), "Nimbus", 8.2),
          ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8)]
    if head:
        st += [("FONT", (0, 0), (-1, 0), "Nimbus-B", 8.2),
               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8ee"))]
    t.setStyle(TableStyle(st))
    return KeepTogether([t, Paragraph(mk(caption), CAP)])

story = []

# ------------------------------------------------------------------ header (same as reference)
def author_grid():
    cells = [Paragraph('<b>%s</b><br/>%s' % (n, e), AUTHCELL) for n, e in AUTHORS]
    pos = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 1)]
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

header = [Paragraph(mk(TITLE_TXT), TITLE),
          rule(16, 7),
          author_grid(),
          Paragraph(AFFIL, AFF),
          rule(5, 17),
          Paragraph('Abstract', ABSHEAD),
          Paragraph(mk(ABSTRACT), ABS)]
def flowheight(fs):          # wrap() ignores spaceBefore/spaceAfter -> include them
    h = 0.0
    for f in fs:
        h += getattr(f, 'spaceBefore', 0) or 0
        h += f.wrap(TEXTW, 10000)[1]
        h += getattr(f, 'spaceAfter', 0) or 0
    return h

HDRH = flowheight(header) + 26      # no overflow into the columns
HDRGAP = 1                        # header frame -> top of the two columns
fontfile_ok = True

ft = Frame(LM, PH - TM - HDRH, TEXTW, HDRH, id='top',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fl = Frame(LM, BM, COLW, PH - TM - HDRH - HDRGAP - BM, id='l',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fr = Frame(LM + COLW + GUT, BM, COLW, PH - TM - HDRH - HDRGAP - BM, id='r',
           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fl2 = Frame(LM, BM, COLW, PH - TM - BM, id='l2',
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
fr2 = Frame(LM + COLW + GUT, BM, COLW, PH - TM - BM, id='r2',
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

# ------------------------------------------------------------------ body
story += header + [FrameBreak()]

for h, paras in REF_SECTIONS:
    story.append(Paragraph(h, H1))
    for p in paras:
        story.append(Paragraph(mk(p), BODY))

story.append(Paragraph('5.&nbsp;&nbsp;Implementation', H1))
story.append(Paragraph(mk(
 "The thermal half of the deck has been built and validated end to end. The sensing node samples the "
 "array ten times a second and pushes each frame over TLS to a server that stores only the raw grid and "
 "regenerates every image element per frame; any browser then displays the result, and a phone camera "
 "reuses the same field as a live overlay."), BODY))

story.append(Paragraph('5.1&nbsp;&nbsp;Prototype construction', H2))
story.append(Paragraph(mk(
 "The prototype is deliberately minimal: one sensor, one controller and a phone, all obtainable "
 "locally. Table 1 lists the elements and the interface each presents."), BODY))
story.append(fig('col_arch.png',
 "Fig. 1. System architecture. The sensing node streams raw 8&times;8 temperature grids to the server; "
 "rendering is server-side, so clients receive plain PNGs. The camera path reuses the same normalised "
 "field, keeping the overlay and the panes in agreement."))
story.append(table([
    [Paragraph('<b>Element</b>', BODY), Paragraph('<b>Part</b>', BODY), Paragraph('<b>Function</b>', BODY)],
    [Paragraph('Thermal sensor', BODY), Paragraph('Panasonic AMG8833, 8&times;8, 60&deg; FOV',
      BODY), Paragraph('absolute temperature grid over I&sup2;C (400&nbsp;kHz)', BODY)],
    [Paragraph('Controller', BODY), Paragraph('ESP32 DevKit V1, 240&nbsp;MHz', BODY),
     Paragraph('samples the array, TLS uplink at 10&nbsp;fps', BODY)],
    [Paragraph('Interconnect', BODY), Paragraph('solderless breadboard, jumper leads', BODY),
     Paragraph('3V3 rail, I&sup2;C bus, status LED', BODY)],
    [Paragraph('Power', BODY), Paragraph('5&nbsp;V USB', BODY),
     Paragraph('single-cable supply for the whole node', BODY)],
    [Paragraph('Viewfinder', BODY), Paragraph('unmodified phone camera', BODY),
     Paragraph('live overlay and image capture', BODY)],
    [Paragraph('Compute', BODY), Paragraph('x86 host, Ubuntu', BODY),
     Paragraph('rendering, streaming, identification, pricing', BODY)],
], [COLW*0.22, COLW*0.38, COLW*0.40],
 "<b>Table 1.</b> Elements of the working prototype."))

story.append(Paragraph('5.2&nbsp;&nbsp;Firmware and frame protocol', H2))
story.append(Paragraph(mk(
 "Each frame is 128&nbsp;bytes: 64 signed 16-bit integers in little-endian order, representing degrees "
 "Celsius &times;&nbsp;100 (Fig. 2). This is a lossless representation of the sensor's own output, it "
 "needs no parsing beyond a memory cast, and it costs 1.28&nbsp;kB/s of uplink at the sensor's full "
 "10&nbsp;fps. Frames are pushed over a persistent TLS connection with a token header, and the firmware "
 "drains responses continuously so that the server's writes cannot block the socket."), BODY))
story.append(fig('col_schematic.png',
 "Fig. 2. Sensing front-end. SDA, SCL and INT run between the two boards; the sensor shares the "
 "3.3&nbsp;V rail, the bus runs at 400&nbsp;kHz with 4.7&nbsp;k&Omega; pull-ups, and its address is 0x69 "
 "(ADO tied low). Only four wires are required."))
story.append(fig('col_packet.png',
 "Fig. 3. Wire format: 128 bytes = 64 &times; int16, &deg;C &times; 100."))

story.append(Paragraph('5.3&nbsp;&nbsp;Server-side rendering', H2))
story.append(Paragraph(mk(
 "Storing only the raw grid and rendering on the server has two consequences. First, the same normalised "
 "field feeds the colour mapping, the shape segmentation, the hotspot decision and the camera overlay, "
 "so the panes and the overlay cannot disagree. Second, the client becomes trivial, which is what makes "
 "a phone a viable display."), BODY))
story.append(fig('col_pipeline.png',
 "Fig. 4. Rendering pipeline: one pass per frame (stack, orient, normalise, stretch, resample, dither, "
 "quantise, contour, segment, pack)."))
story.append(Paragraph(mk(
 "Frames are combined by a sigma-clipped rolling mean whose threshold is k&nbsp;&middot;&nbsp;1.4826"
 "&nbsp;&middot;&nbsp;MAD, floored at 0.15&nbsp;&deg;C; the floor exists because a purely statistical "
 "threshold discards genuine small differences, which at 64 samples is indistinguishable from noise. "
 "The field is normalised through a colour window that is automatic or manual; the automatic window uses "
 "the 5th and 95th percentiles rather than the extremes, so a stray cell cannot wash the frame to a "
 "single colour, and the window is smoothed so that it cannot snap between frames. A global asinh "
 "stretch compresses the warm end, additive local contrast follows, and the 8&times;8 field is upsampled "
 "to 256&times;256, dithered to suppress banding across 32 levels, and packed into a 65-colour PNG. "
 "Contour lines are pre-composited 20&nbsp;% darkened twins of each palette entry, and the hot region "
 "is outlined with a threshold chosen by Otsu's method on the same normalised field."), BODY))
story.append(fig('col_detection.png',
 "Fig. 5. Colour response and localisation. Top: the palette (cyan to red). Bottom: an 8&times;8 field, "
 "its bicubic upsampling through the palette, and the Otsu outline with the hottest cell boxed."))

story.append(Paragraph('5.4&nbsp;&nbsp;Camera overlay, identification and sourcing', H2))
story.append(Paragraph(mk(
 "The diagnosis is easier to trust when the heat is drawn on the object that produced it. The phone "
 "camera becomes the viewfinder and the thermal field is warped onto it with a single affine transform "
 "(translation, scale, rotation, mirror), captured once by dragging the overlay onto something hot. "
 "Fig. 5 shows the overlay in operation."), BODY))
story.append(fig('1792236081738.jpg',
 "Fig. 6. The live camera overlay in use. The 8&times;8 field is warped onto the phone's view; the "
 "marked cell reads 30.5&nbsp;&deg;C.", w=COLW*0.84, photo=True))
story.append(Paragraph(mk(
 "Because the overlay hides exactly the detail a vision model needs, each capture stores the composited "
 "frame for the record and a second, clean frame which is what the model sees. The model returns the "
 "component type, any legible part number, the package and a confidence; a web-search pass then locates "
 "that part on Amazon.in or Flipkart and returns a price in rupees, restricted to an actual product "
 "page. Fig. 6 shows a recorded diagnosis."), BODY))
story.append(fig('1792234036968.jpg',
 "Fig. 7. A recorded diagnosis. The photograph carries its hotspot temperature, the identified component "
 "and a sourced price; the overlay is composited in, so the record is self-explanatory.",
 w=COLW*0.84, photo=True))

story.append(Paragraph('6.&nbsp;&nbsp;Results', H1))
story.append(Paragraph(mk(
 "The prototype has run continuously against a live sensor and a public endpoint. The uplink requirement "
 "is negligible at 1.28&nbsp;kB/s, so the instrument can be operated over a mobile hotspot. Rendering "
 "cost is borne by the server and fell substantially once contour lines were pre-composited, removing "
 "the need for an alpha channel and shrinking a pane from 10.3&nbsp;kB to 6.4&nbsp;kB."), BODY))
story.append(table([
    [Paragraph('<b>Quantity</b>', BODY), Paragraph('<b>Value</b>', BODY)],
    [Paragraph('Array resolution', BODY), Paragraph('8 &times; 8 (64 cells)', BODY)],
    [Paragraph('Frame and uplink', BODY), Paragraph('128 B at 10 fps = 1.28 kB/s', BODY)],
    [Paragraph('Rendered pane', BODY), Paragraph('6.4 kB PNG (256&times;256, 65 colours)', BODY)],
    [Paragraph('Display update', BODY), Paragraph('internally 30 fps, sensor-limited to 10 fps', BODY)],
    [Paragraph('Identification latency', BODY), Paragraph('about 10 to 13 s per photograph', BODY)],
    [Paragraph('Identification cost', BODY), Paragraph('about &#8377;1 per photograph', BODY)],
], [COLW*0.44, COLW*0.56], "<b>Table 2.</b> Prototype characteristics measured on the live system."))

story.append(Paragraph('7.&nbsp;&nbsp;Discussion and Limitations', H1))
for b, txt in [
 ("Resolution.", "The 8&times;8 array is the dominant limitation. At a 60&deg; field of view each cell "
  "subtends about 7.5&deg;, so a cell covers several components at normal working distance; the "
  "MLX90640's 768 pixels, a twelve-fold increase, is the single highest-value upgrade."),
 ("Energising.", "Everything reported here observes heat. The deck's central claim is that it can cause "
  "the heat to appear at the faulty device by injecting a current-limited rail. The useful current "
  "ceiling depends on the appliance class under test, so the instrument exposes it as an operator "
  "control rather than fixing it in firmware."),
 ("Offline operation.", "The deck is specified as a shop instrument that should work without a network. "
  "Here rendering is centralised and identification calls a remote model, which keeps the field unit "
  "cheap but makes the shop's uplink a dependency; on-device inference and a cached catalogue are the "
  "route to full offline operation."),
 ("Identification is advisory.", "A vision model reading a phone photograph usually returns the type of "
  "a component rather than its exact part number, unless a marking is legible, and a web-search price is "
  "an estimate rather than a quotation. Both are presented as suggestions with a verification link."),
 ("Safety.", "Injecting current into an unknown board is not risk-free. The limiter bounds total power, "
  "but reverse polarity, damaged rails and mains-referenced primaries remain hazards; the deck is "
  "intended for low-voltage secondary-side diagnosis only."),
]:
    story.append(Paragraph(mk("<b>%s</b> %s" % (b, txt)), BODY))

story.append(Paragraph('8.&nbsp;&nbsp;Future Work', H1))
for t in ["Replace the 8&times;8 array with a 32&times;24 MLX90640 and re-validate localisation on dense boards.",
          "Extend the tray instrumentation so the injected current is logged alongside the thermal frame, "
          "allowing short and open faults to be classified automatically.",
          "Move identification on-device and cache datasheets and part pricing for offline operation.",
          "Generate the desoldering guide automatically from the identified package and the board "
          "photograph, and evaluate the deck with working repair technicians rather than in the lab."]:
    story.append(Paragraph(mk(t), BUL, bulletText='\u2022'))

story.append(Paragraph('9.&nbsp;&nbsp;Conclusion', H1))
story.append(Paragraph(mk(
 "The economics of electronics repair are distorted by an information problem: the failure is local, but "
 "proving it is not cheap. A deck that energises a board safely and images where the power goes turns "
 "that local failure into a visible, shareable fact, and reduces the repair from a &#8377;15,000 board "
 "replacement to a &#8377;50 part. The prototype presented here implements the thermal half of that "
 "instrument as a streaming web service and demonstrates the complete reasoning chain: image the board, "
 "mark the hot component, name it, price it."), BODY))

story.append(Paragraph('References', H1))
for i, r in enumerate([
 "Panasonic Industry, &ldquo;Grid-EYE Infrared Array Sensor AMG8833,&rdquo; datasheet, Rev. 2.0.",
 "Melexis, &ldquo;MLX90640 32&times;24 IR Array,&rdquo; datasheet, Rev. 10.",
 "N. Otsu, &ldquo;A threshold selection method from gray-level histograms,&rdquo; IEEE Trans. Systems, "
 "Man, and Cybernetics, vol. 9, no. 1, pp. 62-66, 1979.",
 "K. Zuiderveld, &ldquo;Contrast limited adaptive histogram equalization,&rdquo; Graphics Gems IV, "
 "Academic Press, 1994, pp. 474-485.",
 "Espressif Systems, &ldquo;ESP32 Series Datasheet,&rdquo; v4.x.",
 "WHATWG, &ldquo;HTML Living Standard: Server-sent events.&rdquo;",
], 1):
    story.append(Paragraph(mk("[%d]&nbsp;&nbsp;%s" % (i, r)), REF))

# ------------------------------------------------------------------ build
OUT = os.path.join(HERE, 'Board-Rescuer-Deck.pdf')
doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=LM, rightMargin=RM,
                      topMargin=TM, bottomMargin=BM, title=TITLE_TXT,
                      author=', '.join(a[0] for a in AUTHORS))
doc.addPageTemplates([PageTemplate(id='first', frames=[ft, fl, fr], onPage=footer),
                      PageTemplate(id='later', frames=[fl2, fr2], onPage=footer)])
doc.build([NextPageTemplate('later')] + story)
print('built', OUT)
