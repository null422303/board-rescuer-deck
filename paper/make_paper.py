#!/usr/bin/env python3
"""Render the Right-to-Repair Board Rescuer Deck paper to PDF (two-column, IEEE-ish).
Usage: python3 make_paper.py   ->  Board-Rescuer-Deck.pdf
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Image, NextPageTemplate, KeepTogether, Table, TableStyle, HRFlowable)

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
PHO = os.path.join(HERE, "photos")

# ---------------------------------------------------------------- fonts
FONTDIRS = [os.path.join(HERE, "fonts"), "/tmp/replay/fonts"]
def fontfile(n):
    for d in FONTDIRS:
        p = os.path.join(d, n)
        if os.path.exists(p):
            return p
    raise SystemExit("missing font " + n)

pdfmetrics.registerFont(TTFont("Nimbus",    fontfile("NimbusRoman-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Nimbus-B",  fontfile("NimbusRoman-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Nimbus-I",  fontfile("NimbusRoman-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Nimbus-BI", fontfile("NimbusRoman-BoldItalic.ttf")))
pdfmetrics.registerFontFamily("Nimbus", normal="Nimbus", bold="Nimbus-B",
                              italic="Nimbus-I", boldItalic="Nimbus-BI")
pdfmetrics.registerFont(TTFont("NotoSans", fontfile("NotoSans-Regular.ttf")))

INK   = colors.HexColor("#14141f")
MUTED = colors.HexColor("#5b5b70")
ACC   = colors.HexColor("#c8102e")
LINE  = colors.HexColor("#c9c9d4")

def S(name, **kw):
    base = dict(fontName="Nimbus", fontSize=10, leading=11.6, textColor=INK,
                alignment=TA_JUSTIFY, spaceAfter=4.2,
                hyphenationLang="en_GB", spaceShrinkage=0.08)
    base.update(kw)
    return ParagraphStyle(name, **base)

TITLE  = S("t", fontName="Nimbus-B", fontSize=16.5, leading=19.5, alignment=TA_CENTER,
           textColor=INK, spaceAfter=3)
SUB    = S("s", fontName="Nimbus", fontSize=10, leading=12, alignment=TA_CENTER,
           textColor=MUTED, spaceAfter=6)
AUTH   = S("a", fontName="Nimbus-B", fontSize=9.4, leading=12.4, alignment=TA_CENTER, spaceAfter=1)
MAIL   = S("m", fontName="Nimbus", fontSize=7.3, leading=9.6, alignment=TA_CENTER,
           textColor=MUTED, spaceAfter=2)
AFF    = S("af", fontName="Nimbus-I", fontSize=8.6, leading=11, alignment=TA_CENTER,
           textColor=INK, spaceAfter=8)
H1     = S("h1", fontName="Nimbus-B", fontSize=10.6, leading=13, alignment=TA_LEFT,
           textColor=INK, spaceBefore=7, spaceAfter=3)
H2     = S("h2", fontName="Nimbus-B", fontSize=9.4, leading=11.6, alignment=TA_LEFT,
           textColor=INK, spaceBefore=5, spaceAfter=2.4)
ABS    = S("ab", fontSize=9.6, leading=11.2, leftIndent=18*mm, rightIndent=18*mm)
CAP    = S("c", fontName="Nimbus", fontSize=7.6, leading=9.8, alignment=TA_CENTER,
           textColor=MUTED, spaceBefore=2.5, spaceAfter=7)
REF    = S("r", fontSize=7.7, leading=9.6, alignment=TA_LEFT, spaceAfter=2.4,
           leftIndent=6, firstLineIndent=-6)
BUL    = S("b", fontSize=9.0, leading=11.8, leftIndent=8, bulletIndent=1, spaceAfter=1.8)
CODE   = S("cd", fontName="Nimbus", fontSize=7.6, leading=10, alignment=TA_LEFT,
           textColor=colors.HexColor("#20304a"), backColor=colors.HexColor("#f3f4f8"),
           borderPadding=4, spaceAfter=5)

def mk(t):
    t=t.replace("&#8377;","\u20b9")
    t=t.replace("\u20b9","<font name=\"NotoSans\">\u20b9</font>")
    return t
def body(t):  return Paragraph(mk(t), S("x"))
def h1(t):    return Paragraph(t, H1)
def h2(t):    return Paragraph(t, H2)
def cap(t):   return Paragraph(t, CAP)

def fig(path, width_mm, caption, scale=1.0):
    from PIL import Image as PILImage
    p = os.path.join(FIG if not path.startswith("ph:") else PHO,
                     path[3:] if path.startswith("ph:") else path)
    iw, ih = PILImage.open(p).size
    w = width_mm * mm
    h = w * ih / iw * scale
    im = Image(p, width=w, height=h)
    return KeepTogether([im, cap(caption)])

# ---------------------------------------------------------------- document
PW, PH = letter
M     = 54.0
TEXTW = PW - 2 * M            # single-column measure; figures are sized to this
COLW  = TEXTW

class Doc(BaseDocTemplate):
    def __init__(self, fn):
        super().__init__(fn, pagesize=letter, leftMargin=M, rightMargin=M,
                         topMargin=M, bottomMargin=16 * mm, title="The Right-to-Repair Board Rescuer Deck",
                         author="Johnsteven R et al.")
        full = Frame(M, 16 * mm, TEXTW, PH - M - 16 * mm, id="body",
                     leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="first", frames=[full], onPage=self._foot),
                               PageTemplate(id="rest",  frames=[full], onPage=self._foot)])

    def _foot(self, canv, doc):
        canv.saveState()
        canv.setFont("Nimbus", 7.2)
        canv.setFillColor(MUTED)
        canv.drawCentredString(PW / 2, 8 * mm, str(canv.getPageNumber()))
        canv.restoreState()

story = []
A = story.append

# ---- header (title / rule / author grid / affiliation / rule / Abstract)
AUTHORS = [
    ("Johnsteven R",      "johnsteven.r2026@vitstudent.ac.in"),
    ("Pranav Charan B",   "pranavcharan.b2026@vitstudent.ac.in"),
    ("S Raaghav Ayyavoo", "raaghavayyavoo.s2026@vitstudent.ac.in"),
    ("Maarthi P",         "maarthi.p2026@vitstudent.ac.in"),
    ("N Akilan Gautham",  "akilangautham.n2026@vitstudent.ac.in"),
    ("M Dharshan Bagath", "dharshanbagath.m2026@vitstudent.ac.in"),
    ("T D Asvin",         "asvin.td2026@vitstudent.ac.in"),
]
AUTHCELL = S("ac", fontName="Nimbus", fontSize=8.8, leading=10.4, alignment=TA_CENTER)
RULE = colors.HexColor("#666666")
def hrule(sb, sa):
    return HRFlowable(width="100%", thickness=0.6, color=RULE,
                      spaceBefore=sb, spaceAfter=sa, lineCap="butt")


def author_grid():
    cells = [Paragraph("<b>%s</b><br/>%s" % (n, e), AUTHCELL) for n, e in AUTHORS]
    pos = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 1)]
    grid = [[Paragraph("", AUTHCELL) for _ in range(3)] for _ in range(3)]
    for (r, c), cell in zip(pos, cells):
        grid[r][c] = cell
    t = Table(grid, colWidths=[TEXTW / 3.0] * 3, hAlign="CENTER")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                           ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


A(Paragraph(mk("The Right-to-Repair Board Rescuer Deck"), TITLE))
A(hrule(4, 4))
A(author_grid())
A(Paragraph("Vellore Institute of Technology, Chennai, Tamil Nadu, India",
            S("af", fontName="Nimbus", fontSize=9.8, leading=11.6, alignment=TA_CENTER,
              spaceAfter=2)))
A(hrule(4, 10))
A(Paragraph("Abstract", S("ah", fontName="Nimbus-B", fontSize=11.5, leading=13.5,
                          alignment=TA_CENTER, spaceBefore=1, spaceAfter=3)))
A(Paragraph(mk("Electronic control boards in modern appliances and vehicles are routinely declared "
  "unrepairable: a single short-circuited power semiconductor worth a few tens of rupees leads a "
  "technician to recommend replacing an entire motherboard costing thousands. This paper presents the "
  "Right-to-Repair Board Rescuer Deck, a portable diagnostic platform aimed at neighbourhood repair "
  "shops (repair-walas) and DIY consumers. The key insight is that failed power semiconductors expose "
  "themselves through localised thermal and electrical signatures when the board is energised at a "
  "safe, low voltage. The deck combines a low-cost thermal-imaging array (MLX90640) with automated "
  "multimeter probes in a testing tray, and uses edge AI to localise the faulty device, identify its "
  "part number, retrieve a datasheet, and display a step-by-step desoldering and replacement guide. "
  "The approach reduces repair cost from whole-board replacement to component-level substitution, "
  "extending device lifetime and cutting electronic waste."), ABS))

A(NextPageTemplate("rest"))

# ============================================================ 1
A(h1("1. The Average Person's Problem"))
A(body("When a washing machine, a modern microwave, or a car dashboard breaks, the local repairman "
  "usually says, &ldquo;The whole motherboard is dead, you need to buy a new one for &#8377;15,000.&rdquo; "
  "In reality, a single &#8377;50 power semiconductor - a MOSFET or a voltage regulator - has "
  "short-circuited. Manufacturers use proprietary software to lock down diagnostics, forcing consumers "
  "into expensive replacements."))
A(body("The gap between the cost of the failed part and the price of the repair is the core economic "
  "problem. A transistor or regulator costs between &#8377;10 and &#8377;100, yet a board replacement for "
  "a washing machine or dashboard can be quoted at &#8377;8,000 to &#8377;20,000. Because the board is "
  "sealed or undocumented, the technician cannot cheaply prove that the fault is localised, so "
  "serviceable hardware becomes electronic waste. Manufacturers reinforce this with proprietary "
  "diagnostics, serialised parts, and software locks that reject replacements."))

A(h1("2. The Semiconductor Connection"))
A(body("Modern appliance boards are packed with microcontrollers and power semiconductors. When they "
  "fail, they usually fail &ldquo;short&rdquo; or &ldquo;open&rdquo;, creating a detectable thermal or "
  "electrical signature."))
A(body("Power semiconductors fail most often because they carry the largest currents and dissipate the "
  "most heat. A MOSFET switching a motor can fail as a drain-to-source short, while a regulator or "
  "rectifier can fail short, open, or drift out of specification after mains transients, inrush "
  "current, thermal cycling, moisture, or ageing. A shorted device draws abnormal "
  "current and becomes a localised hot spot within seconds, because that is where electrical energy "
  "becomes heat; an open device instead removes current from a whole rail. A safe, current-limited low "
  "voltage can therefore reveal either fault, and the two failure modes are distinguishable by the "
  "shape of the thermal and current response."))

# ============================================================ 3
A(h1("3. Proposed Solution"))
A(body("We propose a portable <i>Right-to-Repair Board Rescuer Deck</i> for local repair shops and DIY "
  "consumers. The deck is a laptop-like instrument: its lid houses a low-cost thermal array and a camera "
  "for part-number recognition; its base holds a testing tray, retractable multimeter probes, and a "
  "current-limited power supply. A single-board computer and touchscreen run the diagnosis locally, and "
  "the unit is built from widely available parts so that it stays affordable and works offline."))
A(body("In use, the operator places the suspect board on the tray, where spring-loaded probes contact "
  "its main power rails. The deck energises it at a safe, current-limited voltage while capturing a "
  "thermal image. A vision pipeline compares each frame with an ambient baseline, flags regions that "
  "exceed a temperature threshold, and overlays their coordinates. The hottest anomaly is almost always "
  "the shorted device. The deck then reads the part number, retrieves its datasheet, and shows a "
  "three-dimensional guide for desoldering and replacing that exact component."))

A(fig("fig1_architecture.png", 170, "Fig. 1. System architecture. The sensing node streams raw 8&times;8 "
      "temperature grids to the server; rendering happens server-side, so clients receive plain PNGs. "
      "The camera path reuses the same normalised field, keeping the overlay and the panes in agreement."))

A(h1("4. System Design"))
A(h2("4.1 Sensing front-end"))
A(body("The prototype uses a Panasonic AMG8833 Grid-EYE: an 8&times;8 thermopile array with a 60&deg; "
  "field of view, an I&sup2;C interface, and a 10 frames-per-second internal refresh rate "
  "<super>[1]</super>. It is the cheapest way to obtain a calibrated absolute temperature grid, which "
  "matters because the diagnosis depends on <i>absolute</i> temperature rather than contrast. Fig. 2 "
  "shows the front-end: the sensor shares the 3.3&nbsp;V rail with the ESP32, I&sup2;C runs at 400&nbsp;kHz "
  "with 4.7&nbsp;k&Omega; pull-ups, and the device address is set to 0x69 by tying ADO to ground."))
A(fig("fig2_schematic.png", 170, "Fig. 2. Sensing front-end schematic. ESP32 &harr; AMG8833 over "
      "I&sup2;C, with bus pull-ups, local decoupling, and a status LED. Only four wires are strictly "
      "required: 3V3, GND, SDA, SCL."))
A(body("The design described in Section 3 upgrades this to a Melexis MLX90640 (32&times;24, 768 pixels) "
  "<super>[2]</super>, because an 8&times;8 grid covers roughly 7.5&deg; per cell and cannot reliably "
  "separate two adjacent small-outline packages on a dense board. The MLX90640 is pin-compatible with "
  "the same I&sup2;C front-end and is a drop-in replacement at the protocol level."))

A(h2("4.2 Fault-reveal energising"))
A(body("Thermal imaging alone is not sufficient: a board that is switched off has no hot spot. The "
  "diagnostic step is therefore to energise the board through a current-limited source so that a "
  "short draws current and converts it to heat locally, while the limiter keeps the total dissipation "
  "bounded and the rest of the board undamaged. Fig. 3 shows the concept: a 0&ndash;12&nbsp;V supply with "
  "an adjustable current ceiling feeds spring probes on the board's main rails, and a shunt provides "
  "the current trace that is correlated with the thermal frame. The injected current is logged "
  "alongside the thermal image, which is what separates a short from an open fault: a short draws "
  "abnormal current and concentrates the dissipation in one device, whereas an open removes current "
  "from a whole rail and produces no hot spot at all."))
A(fig("fig3_injection.png", 170, "Fig. 3. Fault-reveal concept. Energising at a safe, current-limited "
      "voltage converts an invisible short into a localised hot spot that the array can localise."))

# ============================================================ 5
A(h1("5. Implementation"))
A(body("We built the thermal half of the deck end-to-end and exposed it as a web application, which "
  "lets the same instrument be driven from a &#8377;0 client (any phone) instead of a dedicated "
  "touchscreen computer. The ESP32 firmware samples the array and posts a frame every 100&nbsp;ms; the "
  "server stores only the raw grid and regenerates every image element each frame."))

A(h2("5.1 Prototype construction"))
A(body("The prototype is built from parts that any repair shop or student can obtain locally, and "
  "is deliberately minimal: one sensor, one controller, and a phone. Table 1 lists the elements of "
  "the working prototype and the interface each one presents."))
bom = Table([
    ["Element", "Part", "Function"],
    ["Thermal sensor", "Panasonic AMG8833, 8\u00d78, 60\u00b0 FOV", "absolute temperature grid over I\u00b2C (400 kHz)"],
    ["Controller", "ESP32 DevKit V1 (D0WD-V3, 240 MHz)", "samples the array, TLS uplink at 10 fps"],
    ["Interconnect", "solderless breadboard, jumper leads", "3V3 rail, I\u00b2C bus, status LED"],
    ["Power", "5 V USB", "single-cable supply for the whole node"],
    ["Viewfinder", "unmodified phone camera", "live overlay and image capture"],
    ["Compute", "x86 host, Ubuntu", "rendering, streaming, identification, pricing"],
], colWidths=[TEXTW * 0.17, TEXTW * 0.42, TEXTW * 0.41])
bom.setStyle(TableStyle([
    ("FONT", (0, 0), (-1, 0), "Nimbus-B", 7.6),
    ("FONT", (0, 1), (-1, -1), "Nimbus", 7.4),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20203a")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether([bom, cap("<b>Table 1.</b> Elements of the working prototype.")]))

A(h2("5.2 Firmware and frame protocol"))
A(body("Each frame is 128&nbsp;bytes - 64 signed 16-bit integers in little-endian order, "
  "representing degrees Celsius &times; 100 (Fig. 4). This is a lossless representation of the sensor's "
  "own output, it needs no parsing beyond a memory cast, and it costs only 1.28&nbsp;kB/s of uplink at "
  "the sensor's full 10&nbsp;fps. Frames are pushed over a persistent TLS connection with a token "
  "header; the firmware drains responses continuously so that the server's writes cannot block the "
  "socket, and a watchdog restarts the node if the link stalls <super>[5]</super>."))
A(fig("fig4_packet.png", 150, "Fig. 4. Wire format: 128 bytes = 64 &times; int16, &deg;C &times; 100."))
A(Paragraph("POST /api/ingest  &nbsp;X-Auth-Token: &lt;token&gt;&nbsp;  &nbsp;Content-Length: 128", CODE))

A(h2("5.3 Server-side rendering"))
A(body("Storing only the raw grid and rendering on the server has two consequences that shaped the "
  "design. First, the <i>same</i> normalised field feeds the colour mapping, the shape segmentation, "
  "the hotspot decision, and the camera overlay, so the panes and the overlay can never disagree. "
  "Second, the client is trivial - it receives two PNGs and swaps them - which is what "
  "makes a phone a viable display."))
A(fig("fig5_pipeline.png", 170, "Fig. 5. Rendering pipeline. A single pass per frame: stack, orient, "
      "normalise, stretch, resample, dither, quantise, contour, segment, pack."))
A(body("Frames are combined by a sigma-clipped rolling mean. The clip threshold is "
  "<i>k</i>&nbsp;&middot;&nbsp;1.4826&nbsp;&middot;&nbsp;MAD of the stack, with an absolute floor of "
  "0.15&nbsp;&deg;C: the floor exists because a purely statistical threshold discards genuine small "
  "temperature differences, which at 64 samples is indistinguishable from sensor noise. The field is "
  "then normalised through a colour window that is either automatic or manual; the automatic window "
  "uses the 5th and 95th percentiles rather than the extremes, so a single stray hot or cold cell "
  "cannot drag the window and wash the frame to a single colour, and the window is temporally smoothed "
  "so that it cannot snap between frames."))
A(body("A global asinh stretch (default k = 2) compresses the warm end where thermopile response is "
  "non-linear, followed by additive local contrast <super>[4]</super>. The 8&times;8 field is then upsampled to "
  "256&times;256 with a bicubic kernel, dithered with an 8&times;8 ordered Bayer pattern to suppress "
  "banding across the 32 colour levels, and packed into a 65-colour indexed PNG. Contour lines are "
  "drawn as 20&nbsp;% darkened twins of each palette entry, pre-composited so that no alpha channel is "
  "needed, and the hot region is outlined with a threshold chosen by Otsu's method <super>[3]</super> "
  "on the same normalised field."))
A(fig("fig6_detection.png", 170, "Fig. 6. Colour response and localisation. Top: the palette "
      "(cyan&rarr;green&rarr;yellow&rarr;red). Bottom: an 8&times;8 field, its bicubic upsampling through "
      "the palette, and the Otsu outline with the hottest cell boxed. The threshold is computed on the "
      "rendered field, so the outline and the colours always agree."))

A(h2("5.4 Camera overlay and calibration"))
A(body("The deck's diagnosis is easier to trust when the heat is drawn on the object that produced it. "
  "In the prototype, the phone camera becomes the viewfinder and the thermal field is warped onto it. "
  "Because the sensor is fixed relative to the camera, a single affine transform (translation, scale, "
  "rotation, and mirror) is sufficient; it is captured once by dragging the overlay onto something hot "
  "and is stored per device. Fig. 7 shows the overlay in operation, with the hottest cell marked by a "
  "box, a crosshair, and its absolute temperature."))
A(fig("ph:1792236081738.jpg", 82, "Fig. 7. The live camera overlay in use. The 8&times;8 field is warped "
      "onto the phone's view; the marked cell reads 30.5&nbsp;&deg;C. Aligning the heat to the object is "
      "a five-second operation performed once per mounting geometry."))

A(h2("5.5 Component identification and sourcing"))
A(body("Two properties of the thermal image make automated identification practical. First, a hotspot "
  "is a strong prior: the component to be replaced is the one under the marker. Second, the thermal "
  "overlay is drawn <i>over</i> the part, which hides exactly the detail a vision model needs. The "
  "prototype therefore captures the composited frame for the record and a second, clean frame - "
  "the same view without the heat map, with only the marker - which is sent to the model. The "
  "model returns the component type, any legible part number, the package, and a confidence; a second, "
  "web-search-grounded pass then locates that part on Amazon.in or Flipkart and returns a price in "
  "rupees, restricted to an actual product page rather than a search or comparison listing. The result "
  "is stored with the photograph and shown beneath it, so the diagnosis, the visual evidence, and the "
  "quoted cost remain together (Fig. 8)."))
A(fig("ph:1792234036968.jpg", 82, "Fig. 8. A recorded diagnosis. The photograph carries its hotspot "
      "temperature, the identified component, and a sourced price; the thermal overlay is composited "
      "into the image so the record is self-explanatory."))

# ============================================================ 6
A(h1("6. Results"))
A(body("The prototype has been running continuously against a live sensor, streamed over a public "
  "endpoint, and is summarised in Table 2. The uplink requirement is negligible (1.28&nbsp;kB/s), which "
  "means the instrument can be operated over a mobile hotspot in a repair shop. Rendering cost is borne "
  "by the server and was reduced substantially by pre-compositing the contour lines, which removed the "
  "need for an alpha channel and shrank a single pane from 10.3&nbsp;kB to 6.4&nbsp;kB."))
tbl = Table([
    ["Quantity", "Value"],
    ["Array resolution", "8 x 8 (64 cells)"],
    ["Frame / uplink", "128 B  @ 10 fps  = 1.28 kB/s"],
    ["Rendered pane", "6.4 kB PNG (256 x 256, 65 colours)"],
    ["Stream, contour + astro", "~188 kB/s for two panes"],
    ["Display update", "up to 30 fps (frame-limited by the sensor)"],
    ["Identification latency", "~10-13 s per photograph"],
    ["Identification cost", "~$0.01 per photograph"],
], colWidths=[TEXTW * 0.42, TEXTW * 0.58])
tbl.setStyle(TableStyle([
    ("FONT", (0, 0), (-1, 0), "Nimbus-B", 7.6),
    ("FONT", (0, 1), (-1, -1), "Nimbus", 7.4),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20203a")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
    ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
]))
A(KeepTogether([tbl, cap("<b>Table 2.</b> Prototype characteristics measured on the live system.")]))
A(body("The automatic colour window, the sigma-clip threshold, and the local-contrast gain are all "
  "exposed as live controls and synchronised across connected devices, which turned out to matter "
  "during development: the parameters that make a static scene legible are not the ones that make a "
  "moving phone-held view legible, and being able to change them from the hand holding the phone is "
  "the difference between a tunable instrument and a fixed camera."))

# ============================================================ 7
A(h1("7. Discussion and Limitations"))
A(body("<b>Resolution.</b> The 8&times;8 array is the dominant limitation. At a 60&deg; field of view "
  "each cell subtends about 7.5&deg;, so a cell covers several components at normal working distance. "
  "The MLX90640's 768 pixels - a 12&times; increase - is the single highest-value upgrade."))
A(body("<b>Energising is the real diagnostic.</b> Everything reported here observes heat; the deck's "
  "central claim is that it can <i>cause</i> the heat to appear at the faulty device by injecting a "
  "current-limited rail. The useful current ceiling - enough to reveal a short without "
  "stressing a healthy rail - depends on the appliance class under test, so the instrument "
  "exposes it as an operator control rather than fixing it in firmware."))
A(body("<b>Offline operation.</b> The deck is specified as a shop instrument that should work without "
  "a network. Here rendering is deliberately centralised and identification and pricing call a remote "
  "model, which keeps the field unit cheap but makes the shop's uplink a dependency; moving inference "
  "on-device, and caching the parts catalogue and datasheets, is the route to full offline operation."))
A(body("<b>Identification is advisory.</b> A vision model reading a phone photograph usually returns "
  "the <i>type</i> of a component, not its exact part number, unless a marking is legible; and a "
  "web-search price is an estimate, not a quotation. Both are presented as suggestions with a "
  "verification link rather than as facts."))
A(body("<b>Safety.</b> Injecting current into an unknown board is not risk-free. The limiter bounds "
  "total power, but reverse polarity, damaged rails, and mains-referenced primaries remain hazards; "
  "the deck is intended for low-voltage secondary-side diagnosis only, and isolation is a prerequisite "
  "for anything connected to mains."))

A(h1("8. Future Work"))
story.append(Paragraph("Replace the 8&times;8 array with a 32&times;24 MLX90640 and re-validate "
  "localisation on dense boards.", BUL, bulletText="\u2022"))
story.append(Paragraph("Extend the tray instrumentation so the injected current is logged alongside "
  "the thermal frame, allowing short and open faults to be classified automatically.", BUL, bulletText="\u2022"))
story.append(Paragraph("Move identification on-device and cache datasheets and part pricing for "
  "offline operation.", BUL, bulletText="\u2022"))
story.append(Paragraph("Generate the desoldering guide automatically from the identified package and "
  "the board photograph, and evaluate the deck with working repair technicians rather than in the lab.", BUL, bulletText="\u2022"))

A(h1("9. Conclusion"))
A(body("The economics of electronics repair are distorted by an information problem: the failure is "
  "local, but proving it is not cheap. A deck that energises a board safely and images where the power "
  "goes turns that local failure into a visible, shareable fact, and reduces the repair from a "
  "&#8377;15,000 board replacement to a &#8377;50 part. The prototype presented here implements the "
  "thermal half of that instrument as a streaming web service and demonstrates the complete reasoning "
  "chain - image the board, mark the hot component, name it, price it - on hardware that "
  "costs less than one of the boards it is meant to save."))

A(h1("References"))
for i, r in enumerate([
  "Panasonic Industry, &ldquo;Grid-EYE Infrared Array Sensor AMG8833,&rdquo; datasheet, Rev. 2.0.",
  "Melexis, &ldquo;MLX90640 32&times;24 IR Array,&rdquo; datasheet, Rev. 10.",
  "N. Otsu, &ldquo;A threshold selection method from gray-level histograms,&rdquo; <i>IEEE Trans. "
  "Systems, Man, and Cybernetics</i>, vol. 9, no. 1, pp. 62&ndash;66, 1979.",
  "K. Zuiderveld, &ldquo;Contrast limited adaptive histogram equalization,&rdquo; in <i>Graphics Gems "
  "IV</i>, Academic Press, 1994, pp. 474&ndash;485.",
  "Espressif Systems, &ldquo;ESP32 Series Datasheet,&rdquo; v4.x.",
  "WHATWG, &ldquo;HTML Living Standard - Server-sent events.&rdquo;",
], 1):
    A(Paragraph(f"[{i}] {r}", REF))


doc = Doc(os.path.join(HERE, "Board-Rescuer-Deck.pdf"))
doc.build(story)
print("wrote", doc.filename)
