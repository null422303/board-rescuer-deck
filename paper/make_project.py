# -*- coding: utf-8 -*-
"""
The Right-to-Repair Board Rescuer Deck: our implemented system.

Formatting is the reference theme, measured to the point:
  Letter, Nimbus Roman TTFs, two columns, rules at y=701.9 / 591.3,
  title 16.5 pt at y=57.4, author grid (John first), abstract at 219.1,
  section 1 at 351.8, body pitch 11.6, abstract pitch 11.4.
Only the CONTENT describes what we actually built.
"""
import os, re
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                FrameBreak, NextPageTemplate, Table, TableStyle,
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

# ------------------------------------------------- reference theme (measured)
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
REF = ParagraphStyle('ref', fontName='Nimbus', fontSize=7.5, leading=11.6, alignment=TA_LEFT,
                     spaceAfter=0, leftIndent=9, firstLineIndent=-9)
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

TITLE_TXT = 'The Right-to-Repair Board Rescuer Deck'
AUTHORS = [
    ("Johnsteven R",      "johnsteven.r2026@vitstudent.ac.in"),
    ("Maarthi P",         "maarthi.p2026@vitstudent.ac.in"),
    ("Pranav Charan B",   "pranavcharan.b2026@vitstudent.ac.in"),
    ("S Raaghav Ayyavoo", "raaghavayyavoo.s2026@vitstudent.ac.in"),
    ("N Akilan Gautham",  "akilangautham.n2026@vitstudent.ac.in"),
    ("M Dharshan Bagath", "dharshanbagath.m2026@vitstudent.ac.in"),
    ("T D Asvin",         "asvin.td2026@vitstudent.ac.in"),
]
AFFIL = 'Vellore Institute of Technology, Chennai, Tamil Nadu, India'

ABSTRACT = (
 "Electronic control boards in modern appliances and vehicles are routinely declared unrepairable: a "
 "single short-circuited power semiconductor worth a few tens of rupees leads a technician to recommend "
 "replacing an entire motherboard costing thousands. This paper presents the thermal instrument of the "
 "Right-to-Repair Board Rescuer Deck, built and validated end to end. An ESP32 (a small Wi-Fi microcontroller) and an AMG8833 8x8 "
 "infrared array stream raw temperature grids to a server that renders every image element itself and "
 "sends it to any browser; a phone camera reuses the same field as a live overlay, and each capture is "
 "passed to a vision model that names the device under the hotspot and prices it on Amazon.in or "
 "Flipkart in rupees. The uplink costs 1.28 kB/s, a rendered pane is 6.4 kB, and identification "
 "completes in about ten seconds, so the whole instrument can be driven from a phone over a "
 "mobile hotspot. Captures are kept in a shared gallery and every control is live-synchronised "
 "across handsets."
)

SECTIONS = []

# 1 and 2 are the reference's motivation, kept verbatim
SECTIONS += [
 ('1.&nbsp;&nbsp;The Average Person\u2019s Problem',
  ["When a washing machine, a modern microwave, or a car dashboard breaks, the local repairman usually "
   "says, \u201cThe whole motherboard is dead, you need to buy a new one for &#8377;15,000.\u201d In reality, a "
   "single &#8377;50 power semiconductor (such as a MOSFET or a voltage regulator) has short-circuited. "
   "Manufacturers use proprietary software to lock down diagnostics, forcing consumers into expensive "
   "replacements.",
   "The gap between the cost of the failed part and the price of the repair is the core economic "
   "problem. A transistor or regulator costs between &#8377;10 and &#8377;100, yet a board replacement for a "
   "washing machine or dashboard can be quoted at &#8377;8,000 to &#8377;20,000. Because the board is sealed "
   "or undocumented, the technician cannot cheaply prove that the fault is localised, so serviceable "
   "hardware becomes electronic waste."]),
 ('2.&nbsp;&nbsp;The Semiconductor Connection',
  ["Modern appliance boards are packed with microcontrollers and power semiconductors. When they fail, "
   "they usually fail \u201cshort\u201d or \u201copen\u201d, creating a detectable thermal or electrical signature.",
   "Power semiconductors fail most often because they carry the largest currents and dissipate the most "
   "heat. A MOSFET switching a motor can fail as a drain-to-source short, while a regulator or rectifier "
   "can fail short, open, or drift out of specification after mains transients, inrush current, thermal "
   "cycling, moisture, or ageing. A shorted device draws abnormal current and becomes a localised hot "
   "spot within seconds, whereas an open device removes current from a whole rail, so a safe, "
   "current-limited low voltage can reveal either fault."]),
]

SECTIONS += [
 ('3.&nbsp;&nbsp;The Implemented System',
  ["The deck is a portable instrument: a thermal array and a camera in the lid, a testing tray with "
   "retractable probes and a current-limited supply in the base. This paper reports the half that has "
   "been built and run continuously: the thermal instrument. It is deliberately minimal, one sensor, "
   "one controller and a phone, and it is exposed as a web service so that the display costs nothing "
   "and any handset can drive it. Table 1 lists the elements of the working prototype.",
   "The node pushes frames to a server that stores only the raw 8x8 grid and does all the colouring, "
   "stacking and segmentation itself. One normalised field therefore feeds the colour mapping, the "
   "segmentation, the hotspot decision and the overlay, so they cannot disagree, and the client only "
   "swaps images, which is what makes a phone a viable display."]),
 ('4.&nbsp;&nbsp;The Sensing Node',
  ["The prototype uses a Panasonic AMG8833 Grid-EYE, an 8x8 thermopile array with a 60 degree field of "
   "view, a two-wire data bus and a 10 frame-per-second (fps) internal refresh rate. It is the cheapest way to "
   "obtain a calibrated absolute temperature grid, which matters because the diagnosis depends on "
   "absolute temperature rather than contrast. The sensor shares its 3.3 V rail with an ESP32 DevKit, "
   "and it needs only four wires: power, ground, data and clock. The whole node is powered from a "
   "single USB lead, so there is no separate supply to bring to the bench.",
   "Each frame is 128 bytes: 64 signed 16-bit integers in little-endian order representing degrees "
   "Celsius times one hundred. This is a lossless representation of the sensor's own output, it needs no "
   "parsing beyond a memory cast (reinterpreting the same bytes as integers), and it costs only "
   "1.28 kB/s of uplink at the sensor's full rate. "
   "Frames are posted over a persistent encrypted connection with a token header, and the firmware reads "
   "back every reply as it arrives, because an unread reply would otherwise stall the socket. A "
   "watchdog (a timer that resets the board if it stops making progress) restarts the node if the "
   "link stalls."]),
]

# ---- figures
FIGW = {'col_arch.png': 0.82, 'col_schematic.png': 0.90, 'col_packet.png': 0.80,
        'col_pipeline.png': 0.64, 'col_detection.png': 0.76}

def fig(name, caption, w=None, photo=False):
    if w is None:
        w = COLW * FIGW.get(name, 0.40 if photo else 0.86)
    p = os.path.join(PHOD if photo else FIGD, name)
    iw, ih = PILImage.open(p).size
    return [Spacer(1, 5), Image(p, width=w, height=w * ih / iw), Paragraph(mk(caption), CAP)]

def table(rows, widths, caption):
    """Caption lives in a spanning final row, so it can never be orphaned
    onto the next column while the table body stays behind."""
    rows = [[Paragraph(mk(c.text if hasattr(c, 'text') else str(c)), c.style)
             if isinstance(c, Paragraph) else mk(c) for c in r] for r in rows]
    ncol = len(widths)
    rows.append([Paragraph(mk(caption), CAP)] + ['' for _ in range(ncol - 1)])
    t = Table(rows, colWidths=widths, repeatRows=1)
    last = len(rows) - 1
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Nimbus", 8.2),
        ("FONT", (0, 0), (-1, 0), "Nimbus-B", 8.2),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8ee")),
        ("GRID", (0, 0), (-1, last - 1), 0.4, colors.HexColor("#999999")),
        ("SPAN", (0, last), (-1, last)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("TOPPADDING", (0, last), (-1, last), 4), ("BOTTOMPADDING", (0, last), (-1, last), 0),
    ]))
    return [t]

# ------------------------------------------------- header (reference geometry)
def author_grid():
    cells = [Paragraph('<b>%s</b><br/>%s' % (n, e), AUTHCELL) for n, e in AUTHORS]
    pos = [(0, 1), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
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

def flowheight(fs):
    h = 0.0
    for f in fs:
        h += getattr(f, 'spaceBefore', 0) or 0
        h += f.wrap(TEXTW, 10000)[1]
        h += getattr(f, 'spaceAfter', 0) or 0
    return h

HDRH = flowheight(header) + 26
HDRGAP = 1

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

# ------------------------------------------------- body
story = list(header) + [FrameBreak()]

def emit(sec):
    for head, paras in sec:
        story.append(Paragraph(head, H1))
        for i, p in enumerate(paras):
            story.append(Paragraph(mk(p), BODY))

emit(SECTIONS)                                   # 1..4

# --- 4 figures + Table 1
story.extend(fig('col_arch.png',
 "Fig. 1. System architecture. The sensing node streams raw 8x8 temperature grids to the server; "
 "rendering is server-side, so every client receives ready-made images. The camera path reuses the same normalised "
 "field, keeping the overlay and the panes in agreement."))
story.extend(fig('col_schematic.png',
 "Fig. 2. Sensing front-end. Four wires connect the two boards: 3.3 V, ground, data and clock. "
 "The node is powered from a single USB lead."))
story.extend(table([
    [Paragraph('<b>Element</b>', BODY), Paragraph('<b>Part</b>', BODY), Paragraph('<b>Function</b>', BODY)],
    [Paragraph('Thermal sensor', BODY), Paragraph('Panasonic AMG8833, 8&times;8, 60&deg;', BODY),
     Paragraph('absolute temperature grid over I&sup2;C', BODY)],
    [Paragraph('Controller', BODY), Paragraph('ESP32 DevKit V1, 240 MHz', BODY),
     Paragraph('sampling and encrypted uplink at 10 fps', BODY)],
    [Paragraph('Interconnect', BODY), Paragraph('breadboard, jumper leads', BODY),
     Paragraph('3V3 rail, 400 kHz I&sup2;C bus, status LED', BODY)],
    [Paragraph('Power', BODY), Paragraph('5 V USB', BODY), Paragraph('single-cable supply', BODY)],
    [Paragraph('Viewfinder', BODY), Paragraph('unmodified phone camera', BODY),
     Paragraph('live overlay and image capture', BODY)],
    [Paragraph('Compute', BODY), Paragraph('small server', BODY),
     Paragraph('rendering, streaming, identification, pricing', BODY)],
], [COLW*0.22, COLW*0.38, COLW*0.40], "<b>Table 1.</b> Elements of the working prototype."))
story.extend(fig('col_packet.png',
 "Fig. 3. Wire format: 128 bytes = 64 &times; int16, degrees Celsius &times; 100."))

story.append(Paragraph('5.&nbsp;&nbsp;Server-Side Rendering', H1))
story.append(Paragraph(mk(
 "A frame is averaged with the previous ones after rejecting outliers (a sigma-clipped rolling mean). "
 "The rejection threshold is k times 1.4826 times the median absolute deviation (MAD, a robust measure "
 "of spread that a few bad pixels cannot inflate), floored at 0.15 degrees Celsius; "
 "the floor exists because a purely statistical threshold discards genuine small differences, which at "
 "64 samples are indistinguishable from sensor noise. The field is then normalised through a colour "
 "window that is either automatic or manual. The automatic window uses the 5th and 95th percentiles "
 "rather than the extremes, so a single stray cell cannot drag the window and wash the frame to one "
 "colour, and the window is smoothed across frames so that it cannot snap between them; taking manual "
 "control seeds the sliders from the live window so there is no jump at the handover."), BODY))
story.append(Paragraph(mk(
 "A global asinh stretch (a curve that lifts small values without clipping large ones) compresses the "
 "warm end where thermopile response is non-linear, and additive local contrast (extra brightness "
 "proportional to how far a pixel sits above its local average) brings out small differences without "
 "disturbing the absolute mapping. The 8x8 field is "
 "then upsampled to 256x256 with a bicubic kernel, dithered with an 8x8 ordered Bayer pattern (a fixed threshold tile that trades banding for fine "
 "texture) so the 32 colour levels do not band, and packed into a 65-colour indexed image that "
 "stays small because each pixel stores a palette number rather than a full colour. Contour lines are "
 "pre-composited 20 percent darkened twins of each palette entry, so no alpha channel is needed, and "
 "the hot region is outlined using a threshold picked automatically by Otsu's method (which chooses "
 "the cut that best separates two groups of pixel values) on the same field. Both panes are then sent "
 "as small palette images over a single live feed to the browser, which costs about 188 kB/s for the "
 "pair and needs no repeated requests."), BODY))
story.extend(fig('col_pipeline.png',
 "Fig. 4. Rendering pipeline: one pass per frame, ten times a second."))
story.extend(fig('col_detection.png',
 "Fig. 5. Colour response and localisation. Top: the palette. Below: the raw 8x8 field, the same "
 "field resampled through the palette, and the automatic outline with the hottest cell boxed."))

story.append(Paragraph('6.&nbsp;&nbsp;Camera Overlay and Calibration', H1))
story.append(Paragraph(mk(
 "A diagnosis is easier to trust when the heat is drawn on the object that produced it. In the built "
 "instrument the phone camera is the viewfinder and the thermal field is warped onto it. Because the "
 "sensor is fixed relative to the camera, a single affine transform (one set of translation, scale, "
 "rotation and mirror values, applied to every pixel) is enough; it is captured once by dragging the overlay onto something hot and is kept in the browser's local "
 "storage on the phone itself, so re-alignment after a knock takes about five seconds. The hottest cell carries a box, "
 "a crosshair and its absolute temperature, and the marker is shown during alignment as well, which is "
 "what makes the drag accurate. Alignment can also be done automatically. Two small LEDs at "
 "diagonally opposite corners of the view are the two brightest spots in the frame; each is looked for "
 "inside its own corner of the grid, because the hottest cell elsewhere belongs to the board. Those two "
 "pairs give the scale, rotation and offset in a step, and the third hot point, the fault itself, is "
 "what the mapping then places. If the node stops sending, the panes fall back to a recorded loop that "
 "matches the current render mode, the header reports the link as offline, and live frames resume the "
 "moment the node returns."), BODY))
story.extend(fig('1792236081738.jpg',
 "Fig. 6. The live overlay in use; the marked cell reads 30.5&nbsp;&deg;C.",
 w=COLW*0.38, photo=True))

story.append(Paragraph('7.&nbsp;&nbsp;Identification and Sourcing', H1))
story.append(Paragraph(mk(
 "Two properties of the thermal image make automated identification practical. A hotspot is a strong "
 "prior for where to look, and, less obviously, the overlay hides exactly the detail a vision model "
 "needs. Each capture therefore stores the composited frame for the record and a second, clean frame "
 "with only the marker drawn, which is what the model sees. The model returns the component type, any "
 "legible part number, the package and a confidence. A second pass that is allowed to search the live web then locates "
 "that part on Amazon.in or Flipkart, restricted to an actual product page rather than a search or "
 "comparison listing, and returns a price in rupees; a result whose link is not from those two "
 "marketplaces is discarded rather than shown. Captures are kept in a shared gallery that anyone may "
 "view, while writing to it (capturing or deleting) requires a passcode checked by the server, and the "
 "gallery is capped so that the host cannot fill up. Fig. 7 shows a recorded diagnosis."), BODY))
story.extend(fig('1792234036968.jpg',
 "Fig. 7. A recorded diagnosis: hotspot temperature, identified component and sourced price.",
 w=COLW*0.38, photo=True))

story.append(Paragraph('8.&nbsp;&nbsp;Results', H1))
story.append(Paragraph(mk(
 "The instrument has run continuously against a live sensor and a public endpoint. The uplink is "
 "negligible, so a shop can run it over a mobile hotspot. Rendering cost is borne by the server and fell "
 "once the contour lines were pre-composited: dropping the alpha channel shrank a pane from 10.3 kB to "
 "6.4 kB. Every control is exposed live and synchronised across handsets, which matters because the "
 "parameters that make a static scene legible are not the ones that make a hand-held view legible. A "
 "line of numbers under each pane also reports the minimum, maximum and mean of the frame, so the "
 "reading can be taken without interpreting colours at all. The "
 "whole system runs as a single program on one machine and the phone that drives it holds no "
 "state beyond the calibration constants for its own camera geometry."), BODY))
story.extend(table([
    [Paragraph('<b>Quantity</b>', BODY), Paragraph('<b>Value</b>', BODY)],
    [Paragraph('Array resolution', BODY), Paragraph('8 &times; 8, 60&deg; field of view', BODY)],
    [Paragraph('Frame and uplink', BODY), Paragraph('128 B at 10 fps = 1.28 kB/s', BODY)],
    [Paragraph('Rendered pane', BODY), Paragraph('6.4 kB image, 256&times;256, 65 colours', BODY)],
    [Paragraph('Display refresh', BODY), Paragraph('30 fps user interface, sensor-limited to 10 fps', BODY)],
    [Paragraph('Identification latency', BODY), Paragraph('about 10 to 13 s per photograph', BODY)],
    [Paragraph('Identification cost', BODY), Paragraph('about &#8377;1 per photograph', BODY)],
], [COLW*0.44, COLW*0.56], "<b>Table 2.</b> Measured characteristics of the running system."))

story.append(Paragraph('9.&nbsp;&nbsp;Discussion and Limitations', H1))
for b, t in [
 ("Resolution.", "The 8x8 array is the dominant limitation. At a 60 degree field of view each cell "
  "subtends about 7.5 degrees, so a cell covers several components at normal working distance; a "
  "32x24 array with 768 pixels, a twelve-fold increase, is the single highest-value upgrade."),
 ("Energising.", "Everything reported here observes heat. The deck's central claim is that it can "
  "cause heat to appear at the faulty device by injecting a current-limited rail. The useful current "
  "ceiling depends on the appliance class under test, so it is specified as an operator control "
  "rather than a firmware constant."),
 ("Offline operation.", "The instrument is specified for a shop that should not depend on a network. "
  "Here rendering is centralised and identification calls a remote model, which keeps the field unit "
  "cheap but makes the uplink a dependency; a cached catalogue and on-device inference are the route "
  "to full offline use."),
 ("Advisory results.", "A vision model reading a phone photograph usually returns the type of a "
  "component rather than its exact part number unless a marking is legible, and a web-search price is "
  "an estimate rather than a quotation. Both are presented as suggestions with a verification link."),
 ("The LEDs.", "Automatic alignment assumes the two LEDs are visible and bright. In a brightly lit "
  "workshop they can be lost against the background, and an LED that has only just been switched on "
  "may read below the board's own fault; both cases fall back to the one-off manual drag."),
 ("Speed.", "Identification takes about ten seconds and needs a network, which is slower than a "
  "technician's own eye once he knows the board. Its value is therefore in the first encounter with an "
  "unfamiliar appliance, not in routine work."),
 ("Safety.", "Injecting current into an unknown board is not risk-free: a limiter bounds total power, "
  "but reverse polarity and mains-referenced primaries remain hazards."),
]:
    story.append(Paragraph(mk("<b>%s</b> %s" % (b, t)), BODY))

story.append(Paragraph('10.&nbsp;&nbsp;Future Work', H1))
for t in ["Move to a 32&times;24 array and re-validate localisation on dense boards.",
          "Instrument the tray so the injected current is logged alongside the thermal frame, allowing "
          "short and open faults to be classified automatically.",
          "Move identification on-device and cache datasheets and part pricing for offline operation.",
          "Generate the desoldering guide from the identified package and the board photograph, and "
          "evaluate the deck with working repair technicians.",
          "Add a second marker for the coolest cell, so that a board with no hotspot can be shown to be "
          "cold rather than merely unremarkable."]:
    story.append(Paragraph(mk(t), BUL, bulletText='\u2022'))

story.append(Paragraph('11.&nbsp;&nbsp;Conclusion', H1))
story.append(Paragraph(mk(
 "The economics of electronics repair are distorted by an information problem: the failure is local, "
 "but proving it is not cheap. An instrument that energises a board safely and images where the power "
 "goes turns that failure into a visible fact, and reduces the repair from a &#8377;15,000 board "
 "replacement to a &#8377;50 part. The system here implements the thermal half of that instrument and "
 "demonstrates the whole reasoning chain on working hardware: image the board, mark the hot component, "
 "name it, price it."), BODY))

story.append(Paragraph('12.&nbsp;&nbsp;Cost and Deployment', H1))
story.append(Paragraph(mk(
 "The instrument costs less than one of the boards it is meant to save. The sensing node is a "
 "microcontroller and one sensor on a breadboard, both bought locally; the server is a single program "
 "on an ordinary machine; and the display is whatever phone the technician already owns. The only "
 "recurring cost is the identification step, about one rupee per photograph and only when the operator "
 "chooses to capture. Nothing has to be installed on the phone, which matters when the people who need "
 "the instrument most are the least likely to install an application."), BODY))
story.append(Paragraph(mk(
 "The same feed serves any number of viewers at once, so a senior technician can watch a junior's board "
 "from another room and a disputed diagnosis can be seen by both parties at the same moment. That is "
 "precisely the argument that is hardest to make with a photograph taken afterwards."), BODY))

story.append(Paragraph('References', H1))
for i, r in enumerate([
 "Adafruit AMG88xx driver: github.com/adafruit/Adafruit_AMG88xx",
 "ESP32 Arduino core: github.com/espressif/arduino-esp32",
 "NumPy: github.com/numpy/numpy",
 "Matplotlib: github.com/matplotlib/matplotlib",
 "ReportLab: reportlab.com",
 "Pyphen: github.com/Kozea/Pyphen",
 "Caddy: github.com/caddyserver/caddy",
 "OpenRouter: openrouter.ai",
 "z-ai/glm-5.3-flash via OpenRouter",
 "N. Otsu, IEEE Trans. SMC 9(1), 1979",
 "K. Zuiderveld, Graphics Gems IV, 1994",
 "WHATWG HTML Standard: Server-sent events",
], 1):
    story.append(Paragraph(mk("[%d]&nbsp;&nbsp;%s" % (i, r)), REF))

OUT = os.path.join(HERE, 'Board-Rescuer-Deck.pdf')
doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=LM, rightMargin=RM,
                      topMargin=TM, bottomMargin=BM, title=TITLE_TXT,
                      author=', '.join(a[0] for a in AUTHORS))
doc.addPageTemplates([PageTemplate(id='first', frames=[ft, fl, fr], onPage=footer),
                      PageTemplate(id='later', frames=[fl2, fr2], onPage=footer)])
doc.build([NextPageTemplate('later')] + story)
print('built', OUT)
