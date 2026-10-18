#!/usr/bin/env python3
"""Generate all figures for the Right-to-Repair Board Rescuer Deck paper.
Light academic style, thermal palette as accent. 300 dpi PNG -> figures/.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

INK   = "#14141f"; MUTED = "#5b5b70"; LINE = "#b9b9c6"
BLUE  = "#2b6cff"; YEL = "#d99a00"; GREEN = "#12a06a"; RED = "#e02b4e"
PAPER = "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                     "axes.edgecolor": LINE, "savefig.facecolor": PAPER, "figure.facecolor": PAPER})

def box(ax, x, y, w, h, text, fc="#f6f7fb", ec=INK, fs=9, bold=False, r=0.02, lw=1.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                linewidth=lw, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=INK, zorder=3, linespacing=1.5)

def arrow(ax, p, q, color=INK, lw=1.2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, linewidth=lw,
                                 color=color, linestyle=ls, zorder=1))

def wire(ax, pts, color=INK, lw=1.1):
    for a, b in zip(pts[:-1], pts[1:]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, zorder=1, solid_capstyle="round")

def gnd(ax, x, y, color=INK):
    ax.plot([x, x], [y, y - .32], color=color, lw=1.1)
    for i, w in enumerate((.30, .20, .11)):
        ax.plot([x - w, x + w], [y - .32 - i * .13, y - .32 - i * .13], color=color, lw=1.3)

def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig); print("wrote", name)

def blank(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    return fig, ax


# ============================================================ FIG 1: architecture
fig, ax = blank(7.2, 3.0)
box(ax, .015, .60, .215, .30, "Sensing node\nESP32 + AMG8833\n8x8 IR array", fc="#eef3ff", ec=BLUE, bold=True)
ax.text(.1225, .545, "10 fps  |  128 B/frame", ha="center", fontsize=7.6, color=MUTED)
box(ax, .015, .13, .215, .28, "Probe tray\ncurrent-limited injection\n+ 4-wire sensing\n(proposed)", fc="#fff8ec", ec=YEL, fs=8.2)
arrow(ax, (.1225, .58), (.1225, .42), color=YEL, ls=(0, (3, 2)))
box(ax, .295, .22, .27, .60,
    "VPS service\n\n64-cell grid stored raw\nsigma-clipped stack\ncolor window + asinh\nbicubic 8->256\ncontour + Otsu outline\npalette PNG",
    fc="#f6f7fb", bold=True, fs=8.4)
arrow(ax, (.235, .75), (.295, .75), color=BLUE, lw=1.6)
ax.text(.265, .80, "TLS", ha="center", fontsize=7.4, color=BLUE)
arrow(ax, (.295, .50), (.235, .50), color=BLUE, lw=1.6)
ax.text(.265, .39, "keep-alive\n10 Hz", ha="center", fontsize=7, color=MUTED)
box(ax, .625, .60, .215, .30, "Browser\nSSE stream\nraw | processed", fc="#f1fbf6", ec=GREEN, bold=True)
box(ax, .625, .13, .215, .30, "Camera overlay\nwarp heat onto the\nphone view; snap", fc="#f1fbf6", ec=GREEN, fs=8.4)
arrow(ax, (.565, .72), (.625, .72), color=GREEN, lw=1.6)
ax.text(.595, .77, "SSE", ha="center", fontsize=7.4, color=GREEN)
arrow(ax, (.625, .28), (.565, .28), color=GREEN, lw=1.6)
ax.text(.595, .17, "JPEG", ha="center", fontsize=7.4, color=GREEN)
box(ax, .875, .60, .11, .30, "Vision\nmodel\nidentify\npart", fc="#fdeef1", ec=RED, bold=True, fs=8)
box(ax, .875, .13, .11, .30, "Live price\namazon.in\nflipkart\nINR", fc="#fdeef1", ec=RED, fs=7.6)
arrow(ax, (.84, .75), (.875, .75), color=RED, lw=1.4)
arrow(ax, (.84, .28), (.875, .28), color=RED, lw=1.4)
arrow(ax, (.93, .58), (.93, .45), color=RED, lw=1.2)
ax.text(.965, .515, "bill of\nmaterials", ha="center", fontsize=6.6, color=RED)
save(fig, "fig1_architecture.png")


# ============================================================ FIG 2: circuit schematic
fig, ax = blank(7.2, 3.4)
ax.set_xlim(0, 10); ax.set_ylim(0, 10)

EX, EW = 0.25, 2.90          # ESP32 board
AX_, AW = 6.85, 2.90         # AMG8833 board
ax.add_patch(Rectangle((EX, 1.5), EW, 6.1, lw=1.4, ec=BLUE, fc="#eef3ff", zorder=2))
ax.text(EX + EW / 2, 7.25, "ESP32 DevKit V1", ha="center", fontsize=9.4, fontweight="bold", color=BLUE)
ax.text(EX + EW / 2, 1.75, "CP2102  -  3.3 V logic", ha="center", fontsize=7.0, color=MUTED)
ax.add_patch(Rectangle((AX_, 2.9), AW, 4.7, lw=1.4, ec=GREEN, fc="#f1fbf6", zorder=2))
ax.text(AX_ + AW / 2, 7.25, "AMG8833 breakout", ha="center", fontsize=9.4, fontweight="bold", color=GREEN)
ax.text(AX_ + AW / 2, 3.14, "0x69 (ADO to GND)  -  60 deg FOV", ha="center", fontsize=7.0, color=MUTED)

SDA_Y, SCL_Y, INT_Y = 5.55, 5.05, 4.55
esp_pins = [("3V3", 6.95), ("GND", 6.45), ("GPIO 21   SDA", SDA_Y), ("GPIO 22   SCL", SCL_Y),
            ("GPIO 4   INT", INT_Y), ("GPIO 2   LED", 2.30)]
for name, y in esp_pins:
    ax.text(EX + EW - .12, y, name, ha="right", va="center", fontsize=7.6)
    ax.plot([EX + EW, EX + EW + .40], [y, y], color=INK, lw=1.1, zorder=3)
amg_pins = [("VIN", 6.95), ("GND", 6.45), ("SDA", SDA_Y), ("SCL", SCL_Y), ("INT", INT_Y), ("ADO", 3.90)]
for name, y in amg_pins:
    ax.text(AX_ + .12, y, name, ha="left", va="center", fontsize=7.6)
    ax.plot([AX_ - .40, AX_], [y, y], color=INK, lw=1.1, zorder=3)

X0, X1 = EX + EW + .40, AX_ - .40          # 3.55 .. 6.45
# 3V3 rail along the top (above both boards) -> no wire crossings anywhere
ax.plot([EX + EW + .40, EX + EW + .40], [6.95, 8.55], color=BLUE, lw=1.2, zorder=1)
ax.plot([EX + EW + .40, 8.55], [8.55, 8.55], color=BLUE, lw=1.2, zorder=1, solid_capstyle="round")
ax.plot([8.55, 8.55], [8.55, 6.95], color=BLUE, lw=1.2, zorder=1)
ax.text(6.55, 8.72, "3.3 V rail", ha="center", fontsize=7.4, color=BLUE)
# ground reference: one symbol per board, on the GND pin
for x in (EX + EW + .40, AX_ - .40):
    ax.plot([x, x], [6.45, 6.13], color=INK, lw=1.1)
    gnd(ax, x, 6.13)
# signals
wire(ax, [(X0, SDA_Y), (X1, SDA_Y)], YEL); ax.text(5.0, SDA_Y + .18, "SDA   I2C data", ha="center", fontsize=7.2, color=YEL)
wire(ax, [(X0, SCL_Y), (X1, SCL_Y)], YEL); ax.text(5.0, SCL_Y + .18, "SCL   I2C clock 400 kHz", ha="center", fontsize=7.2, color=YEL)
wire(ax, [(X0, INT_Y), (X1, INT_Y)], LINE); ax.text(5.0, INT_Y + .18, "INT   optional", ha="center", fontsize=7.0, color=MUTED)
# pull-ups hanging from the 3V3 rail down to the two bus lines (cross nothing)
for x, src in ((4.35, SDA_Y), (5.65, SCL_Y)):
    ax.plot([x, x], [8.55, src], color=YEL, lw=1.0, zorder=1)
    ax.add_patch(Rectangle((x - .11, (8.55 + src) / 2 - .26), .22, .52, lw=1.0, ec=YEL, fc="white", zorder=3))
    ax.text(x + .16, (8.55 + src) / 2, "4k7", fontsize=6.8, va="center", color=YEL)
    ax.plot([x - .06, x + .06], [src, src], color=YEL, lw=1.4)
ax.text(4.35, 8.05, "I2C pull-ups", ha="center", fontsize=6.8, color=YEL)
# status LED
ax.plot([EX + EW + .40, EX + EW + .40], [2.30, 1.90], color=INK, lw=1.0)
ax.plot([EX + EW + .20, EX + EW + .40], [1.90, 1.90], color=INK, lw=1.0)
ax.add_patch(Rectangle((EX + EW + .40, 1.60), .36, .30, lw=1.0, ec=INK, fc="#fff6cc", zorder=3))
ax.text(EX + EW + .85, 1.75, "220R + status LED", fontsize=7.0, va="center", color=MUTED)
gnd(ax, EX + EW + .20, 1.90)
ax.text(5.0, 9.55, "ESP32  \u2194  AMG8833  \u2014  I\u00b2C sensing front-end", ha="center", fontsize=10, fontweight="bold")
ax.text(5.0, 9.05, "3.3 V logic  \u00b7  400 kHz bus  \u00b7  10 frames/s  \u00b7  only four wires are required",
        ha="center", fontsize=7.6, color=MUTED)
save(fig, "fig2_schematic.png")


# ============================================================ FIG 3: injection concept
fig, ax = blank(7.2, 2.9)
ax.set_xlim(0, 10); ax.set_ylim(0, 10)
def blk(x, y, w, h, t, fc, ec, fs=8.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=.08",
                                lw=1.2, ec=ec, fc=fc, zorder=2))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, zorder=3, linespacing=1.5)
blk(.2, 3.2, 2.0, 3.0, "Current-limited\nsupply\n0-12 V, 0-500 mA", "#fff8ec", YEL)
blk(2.6, 3.2, 1.8, 3.0, "Series\nlimiter\n+ shunt", "#fff8ec", YEL)
blk(4.8, 3.2, 2.0, 3.0, "Spring probes\non board rails", "#eef3ff", BLUE)
blk(7.2, 3.2, 2.6, 3.0, "Faulty board\n\nshorted device\nbecomes a hot spot", "#fdeef1", RED, fs=8.0)
arrow(ax, (2.2, 4.7), (2.6, 4.7), YEL, 1.4)
arrow(ax, (4.4, 4.7), (4.8, 4.7), YEL, 1.4)
arrow(ax, (6.8, 4.7), (7.2, 4.7), BLUE, 1.4)
ax.text(7.0, 5.75, "V+, GND", ha="center", fontsize=7.0, color=BLUE)
blk(8.3, 8.35, 1.4, 1.2, "IR array", "#f1fbf6", GREEN, fs=7.8)
arrow(ax, (8.7, 8.30), (8.55, 6.35), GREEN, 1.2, ls=(0, (3, 2)))
ax.text(9.65, 7.35, "thermal\nimage", ha="center", fontsize=7.0, color=GREEN)
ax.text(5.0, 1.6, "Safe, current-limited energising turns an invisible short into a localised hot spot",
        ha="center", fontsize=8.4, style="italic", color=MUTED)
ax.text(5.0, 9.55, "Fault-reveal concept: energise, image, localise", ha="center",
        fontsize=10, fontweight="bold")
save(fig, "fig3_injection.png")


# ============================================================ FIG 4: packet format
fig, ax = blank(7.0, 1.5)
ax.set_xlim(0, 10); ax.set_ylim(0, 3.2)
for i in range(64):
    row, col = divmod(i, 32)
    x, y = .35 + col * .29, 1.35 - row * .62
    ax.add_patch(Rectangle((x, y), .29, .62, lw=.5, ec=LINE, fc="#eef3ff" if row == 0 else "#f6f7fb"))
    if i in (0, 1, 31, 32, 63):
        ax.text(x + .145, y + .31, str(i), ha="center", va="center", fontsize=5.8, color=MUTED)
ax.annotate("", xy=(9.65, 2.28), xytext=(.35, 2.28), arrowprops=dict(arrowstyle="<|-|>", lw=.9, color=BLUE))
ax.text(5.0, 2.52, "128 bytes  =  64 cells  x  int16  (little-endian, \u00b0C x 100)", ha="center", fontsize=8, color=BLUE)
ax.text(.35, .35, "cell 0 = top-left of the sensor grid  \u00b7  POST /api/ingest  \u00b7  header X-Auth-Token",
        fontsize=7.2, color=MUTED)
save(fig, "fig4_packet.png")


# ============================================================ FIG 5: pipeline (3 rows x 4)
fig, ax = blank(7.2, 4.0)
ax.set_xlim(0, 10); ax.set_ylim(0, 10)
rows = [
    [("POST /api/ingest\n128 B -> 8x8 \u00b0C", "#eef3ff", BLUE),
     ("rolling stack\n\u03c3-clip, 0.15 \u00b0C floor", "#eef3ff", BLUE),
     ("flip 180\u00b0 + mirror", "#f6f7fb", INK),
     ("colour window\nauto 5-95 %ile", "#f6f7fb", INK)],
    [("asinh stretch\n+ local contrast", "#f6f7fb", INK),
     ("bicubic 8 -> 256\n+ unsharp", "#f6f7fb", INK),
     ("ordered dither\n+ quantise 32", "#f6f7fb", INK),
     ("contour lines\n20 % black twins", "#f6f7fb", INK)],
    [("Otsu outline\nof the hot shape", "#f1fbf6", GREEN),
     ("65-colour indexed\npalette PNG", "#f1fbf6", GREEN),
     ("SSE push\n{raw, proc, g8, p8}", "#eef3ff", BLUE),
     ("hotspot alarm\n+ gallery / AI", "#fdeef1", RED)],
]
BW, BH, GX = 2.16, 1.62, 0.34
ys = [7.25, 4.25, 1.25]
for r, (row, y) in enumerate(zip(rows, ys)):
    rtl = (r % 2 == 1)                       # snake the flow: row 1 runs right -> left
    for c, (t, fc, ec) in enumerate(row):
        x = 0.35 + (c if not rtl else 3 - c) * (BW + GX)
        ax.add_patch(FancyBboxPatch((x, y), BW, BH, boxstyle="round,pad=0,rounding_size=.07",
                                    lw=1.15, ec=ec, fc=fc, zorder=2))
        ax.text(x + BW / 2, y + BH / 2, t, ha="center", va="center", fontsize=7.4,
                zorder=3, linespacing=1.5)
        if c < 3:                            # arrow to the next box in flow order
            if rtl:
                arrow(ax, (x, y + BH / 2), (x - (BW + GX) + BW, y + BH / 2), ec, 1.1)
            else:
                arrow(ax, (x + BW, y + BH / 2), (x + BW + GX, y + BH / 2), ec, 1.1)
    if r < 2:                                # drop into the next row at the row's end
        xa = (0.35 + 3 * (BW + GX) + BW / 2) if r % 2 == 0 else (0.35 + BW / 2)
        arrow(ax, (xa, y), (xa, ys[r + 1] + BH), BLUE, 1.2)

ax.text(5.0, 9.62, "Server-side rendering pipeline (one pass per frame, 10 fps)", ha="center",
        fontsize=9.8, fontweight="bold")
ax.text(5.0, 9.14, "only the raw 8x8 is stored \u2014 every pixel downstream is regenerated each frame",
        ha="center", fontsize=7.4, color=MUTED)
save(fig, "fig5_pipeline.png")


# ============================================================ FIG 6: LUT + detection
def ramp(f):
    if f < 0.5:
        return (0, int(f * 2 * 255), int((1 - f * 2) * 255))
    x = (f - 0.5) * 2
    return (int(x * 255), int((1 - x) * 255), 0)

from scipy import ndimage
fig = plt.figure(figsize=(7.2, 2.9))
gs = fig.add_gridspec(2, 3, height_ratios=[1, 2.4], hspace=.42, wspace=.28)
axL = fig.add_subplot(gs[0, :])
lut = np.array([[ramp(f) for f in np.linspace(0, 1, 256)]], dtype="uint8")
axL.imshow(lut, aspect="auto"); axL.set_yticks([]); axL.set_xticks([])
for s in axL.spines.values():
    s.set_edgecolor(LINE)
axL.set_xlabel("colour response  (cold \u2192 hot):  cyan \u2192 green \u2192 yellow \u2192 red",
               fontsize=7.4, color=MUTED, labelpad=3)
gy, gx = np.mgrid[0:8, 0:8].astype(float)
field = (np.exp(-(((gx - 5.2) ** 2 + (gy - 2.6) ** 2) / (2 * 1.15 ** 2))) * 0.75
         + np.exp(-(((gx - 2.1) ** 2 + (gy - 5.4) ** 2) / (2 * 1.6 ** 2))) * 0.30
         + np.exp(-(((gx - 0.6) ** 2 + (gy - 1.2) ** 2) / (2 * 2.6 ** 2))) * 0.10)
field = field / field.max()
axA = fig.add_subplot(gs[1, 0])
axA.imshow(field, cmap="gray_r", interpolation="nearest")
axA.set_title("raw 8x8 field", fontsize=7.6, pad=4)
axA.set_xticks(range(8)); axA.set_yticks(range(8))
axA.tick_params(labelsize=5.5, colors=MUTED, length=0)
big = np.clip(ndimage.zoom(field, 32, order=3), 0, 1)
axB = fig.add_subplot(gs[1, 1])
rgb = np.array([[ramp(v) for v in row] for row in big], dtype="uint8")
axB.imshow(rgb); axB.set_title("bicubic 8 \u2192 256 + LUT", fontsize=7.6, pad=4)
axB.set_xticks([]); axB.set_yticks([])
axC = fig.add_subplot(gs[1, 2])
thr = big > (big.mean() + big.std())
edg = np.zeros_like(thr)
edg[1:, :] |= thr[1:, :] & ~thr[:-1, :]; edg[:-1, :] |= thr[:-1, :] & ~thr[1:, :]
edg[:, 1:] |= thr[:, 1:] & ~thr[:, :-1]; edg[:, :-1] |= thr[:, :-1] & ~thr[:, 1:]
out = rgb.copy(); out[edg] = (0, 255, 120)
axC.imshow(out); axC.set_title("Otsu outline + hotspot cell", fontsize=7.6, pad=4)
axC.plot(5.5 * 32 - 16, 2.5 * 32 - 16, marker="s", ms=13, mfc="none", mec=RED, mew=1.6)
axC.set_xticks([]); axC.set_yticks([])
save(fig, "fig6_detection.png")

print("all figures ->", OUT)
