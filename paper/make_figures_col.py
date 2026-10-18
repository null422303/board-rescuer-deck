#!/usr/bin/env python3
"""Column-width figures (3.39 in = 244 pt) for the two-column paper.
Fonts are sized in points so they render legibly at 100 %.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)
INK="#14141f"; MUTED="#5b5b70"; LINE="#b9b9c6"
BLUE="#2b6cff"; YEL="#d99a00"; GREEN="#12a06a"; RED="#e02b4e"
CW = 3.39                                   # column width in inches
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":6.5,"text.color":INK,
                     "savefig.facecolor":"white","figure.facecolor":"white"})

def blank(h):
    fig, ax = plt.subplots(figsize=(CW, h))
    ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
    return fig, ax
def box(ax,x,y,w,h,t,fc="#f6f7fb",ec=INK,fs=6.4,bold=False,r=.015):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle=f"round,pad=0,rounding_size={r}",
                 lw=.8,ec=ec,fc=fc,zorder=2))
    ax.text(x+w/2,y+h/2,t,ha="center",va="center",fontsize=fs,zorder=3,linespacing=1.45,
            fontweight="bold" if bold else "normal")
def arr(ax,p,q,c=INK,lw=.9,ls="-"):
    ax.add_patch(FancyArrowPatch(p,q,arrowstyle="-|>",mutation_scale=7,lw=lw,color=c,
                 linestyle=ls,zorder=1))
def save(fig,n):
    fig.savefig(os.path.join(OUT,n),dpi=600,bbox_inches="tight",pad_inches=.02)
    plt.close(fig); print("wrote",n)

# ---------- architecture (vertical) ----------
fig,ax=blank(2.95)
box(ax,.04,.86,.92,.12,"Sensing node: ESP32 + AMG8833 (8x8 IR)",fc="#eef3ff",ec=BLUE,bold=True,fs=6.5)
ax.text(.47,.820,"TLS, 128 B/frame, 10 fps",ha="right",fontsize=5.6,color=MUTED)
arr(ax,(.5,.855),(.5,.765),BLUE,ls=(0,(2,2)))
box(ax,.04,.38,.92,.38,"VPS service\n\nraw 64-cell grid stored\nsigma-clipped stack, asinh\nbicubic 8 -> 256, dither\ncontour + Otsu outline\npalette PNG",fc="#f6f7fb",bold=True,fs=6.2)
ax.text(.53,.790,"SSE stream",ha="left",fontsize=5.6,color=GREEN)
box(ax,.04,.20,.44,.17,"Browser\nraw | processed",fc="#f1fbf6",ec=GREEN,fs=6.2)
box(ax,.52,.20,.44,.17,"Camera overlay\nwarp heat, snap",fc="#f1fbf6",ec=GREEN,fs=6.2)
arr(ax,(.26,.375),(.26,.345),RED); arr(ax,(.74,.375),(.74,.345),RED)
box(ax,.04,.03,.44,.14,"vision model\nidentifies the part",fc="#fdeef1",ec=RED,fs=5.7)
box(ax,.52,.03,.44,.14,"Amazon.in / Flipkart\nprice in INR",fc="#fdeef1",ec=RED,fs=5.7)
save(fig,"col_arch.png")

# ---------- schematic ---------- (4 wires, USB powered, no pull-ups)
fig,ax=blank(2.15); ax.set_xlim(0,10); ax.set_ylim(1.95,8.4)
E0,E1 = .25,3.55
A0,A1 = 6.45,9.75
YB0,YB1 = 3.30,7.30
ax.add_patch(Rectangle((E0,YB0),E1-E0,YB1-YB0,lw=1.0,ec=BLUE,fc="#eef3ff"))
ax.add_patch(Rectangle((A0,YB0),A1-A0,YB1-YB0,lw=1.0,ec=GREEN,fc="#f1fbf6"))
ax.text((E0+E1)/2,7.02,"ESP32 DevKit",ha="center",va="center",fontsize=5.2,fontweight="bold",color=BLUE)
ax.text((A0+A1)/2,7.02,"AMG8833",ha="center",va="center",fontsize=6.2,fontweight="bold",color=GREEN)
ax.text((A0+A1)/2,3.55,"8x8 IR array",ha="center",fontsize=5.0,color=MUTED)

pins=[("3V3","VIN",6.55,"3.3 V",BLUE),
      ("GND","GND",5.85,"GND",INK),
      ("GPIO 21","SDA",4.90,"data",YEL),
      ("GPIO 22","SCL",4.20,"clock",YEL)]
for lname,rname,y,lab,col in pins:
    ax.plot([E1,E1+.30],[y,y],color=INK,lw=1.0)
    ax.plot([A0-.30,A0],[y,y],color=INK,lw=1.0)
    ax.plot([E1+.30,A0-.30],[y,y],color=col,lw=1.0)
    ax.text(E1-.12,y,lname,ha="right",va="center",fontsize=5.8)
    ax.text(A0+.12,y,rname,ha="left", va="center",fontsize=5.8)
    ax.text(5.0,y+.17,lab,ha="center",fontsize=5.2,color=col)

# USB power feed into the board
ax.plot([1.9,1.9],[YB0,2.72],color=INK,lw=1.5)
ax.add_patch(Rectangle((1.45,2.38),.9,.34,lw=1.1,ec=INK,fc="#dfe3ee",zorder=3))
ax.text(1.9,2.12,"5 V USB power",ha="center",fontsize=5.4,color=INK)
save(fig,"col_schematic.png")

# ---------- injection ----------
fig,ax=blank(2.4)
for i,(t,fc,ec) in enumerate([("Current-limited supply\n0-12 V, 0-500 mA","#fff8ec",YEL),
                              ("Series limiter + shunt","#fff8ec",YEL),
                              ("Spring probes on rails","#eef3ff",BLUE),
                              ("Faulty board: shorted\ndevice becomes hot","#fdeef1",RED)]):
    y=.78-i*.24
    box(ax,.08,y,.84,.18,t,fc=fc,ec=ec,fs=6.2)
    if i<3: arr(ax,(.5,y),(.5,y-.06),INK)
ax.text(.5,.02,"Safe energising turns an invisible short into a hot spot",ha="center",fontsize=5.8,style="italic",color=MUTED)
save(fig,"col_injection.png")

# ---------- packet ----------
fig,ax=blank(1.0); ax.set_xlim(0,10); ax.set_ylim(0,3.4)
for i in range(64):
    r,c=divmod(i,32); x=.35+c*.29; y=1.5-r*.62
    ax.add_patch(Rectangle((x,y),.29,.62,lw=.3,ec=LINE,fc="#eef3ff" if r==0 else "#f6f7fb"))
    if i in (0,63): ax.text(x+.145,y+.31,str(i),ha="center",va="center",fontsize=4.6,color=MUTED)
ax.text(5.0,2.75,"128 bytes = 64 cells x int16 (little-endian, C x 100)",ha="center",fontsize=6.0,color=BLUE)
ax.text(.35,.5,"cell 0 = top-left; POST /api/ingest",fontsize=5.4,color=MUTED)
save(fig,"col_packet.png")

# ---------- pipeline: 3 columns x 4 rows, snaked, no clipping ----------
STEPS=[("ingest","128 B -> 8x8","#eef3ff",BLUE),
       ("stack","sigma-clip","#eef3ff",BLUE),
       ("orient","flip + mirror","#f6f7fb",INK),
       ("colour window","auto 5-95 %","#f6f7fb",INK),
       ("asinh stretch","","#f6f7fb",INK),
       ("local contrast","","#f6f7fb",INK),
       ("resample","bicubic 8->256","#f6f7fb",INK),
       ("dither","ordered","#f6f7fb",INK),
       ("quantise","32 levels","#f6f7fb",INK),
       ("contour lines","","#f6f7fb",INK),
       ("Otsu outline","","#f1fbf6",GREEN),
       ("palette, send","","#fdeef1",RED)]
fig,ax=blank(2.55); ax.set_xlim(0,10); ax.set_ylim(0,10)
BW,BH=2.76,1.45
COLS=[0.10,3.62,7.14]
ROWS=[7.00,5.10,3.20,1.30]
def cell(col,row): return COLS[col],ROWS[row]
# place: col0 top->bottom, col1 bottom->top, col2 top->bottom
order=[(0,0),(0,1),(0,2),(0,3),(1,3),(1,2),(1,1),(1,0),(2,0),(2,1),(2,2),(2,3)]
for (t1,t2,fc,ec),(col,row) in zip(STEPS,order):
    x,y=cell(col,row)
    ax.add_patch(FancyBboxPatch((x,y),BW,BH,boxstyle="round,pad=0,rounding_size=.05",
                                lw=1.0,ec=ec,fc=fc,zorder=2))
    label=t1 + ("\n"+t2 if t2 else "")
    ax.text(x+BW/2,y+BH/2,label,ha="center",va="center",fontsize=5.4,zorder=3,linespacing=1.5)
def arr(p,q,c):
    ax.add_patch(FancyArrowPatch(p,q,arrowstyle="-|>",mutation_scale=6,lw=.8,color=c,zorder=1))
for i,((t1,t2,fc,ec),(col,row)) in enumerate(zip(STEPS,order)):
    if i==len(STEPS)-1: break
    nc,nr=order[i+1]
    x,y=cell(col,row); nx,ny=cell(nc,nr)
    if nc==col:                                  # vertical step
        if nr>row: arr((x+BW/2,y),(x+BW/2,ny+BH),ec)
        else:      arr((x+BW/2,y+BH),(x+BW/2,ny),ec)
    else:                                        # across to the next column
        arr((x+BW,y+BH/2),(nx,ny+BH/2),ec)
ax.text(5.0,9.35,"Server-side rendering pipeline",ha="center",fontsize=6.2,fontweight="bold")
ax.text(5.0,8.85,"one pass per frame, ten times a second",ha="center",fontsize=5.4,color=MUTED)
save(fig,"col_pipeline.png")

# ---------- detection: palette strip + three panels in a row (short) ----------
def ramp(f):
    if f<0.5: return (0,int(f*2*255),int((1-f*2)*255))
    x=(f-0.5)*2; return (int(x*255),int((1-x)*255),0)
from scipy import ndimage
fig=plt.figure(figsize=(CW,1.62))
gs=fig.add_gridspec(2,3,height_ratios=[.42,1.0],hspace=.42,wspace=.18)
axL=fig.add_subplot(gs[0,:])
axL.imshow(np.array([[ramp(f) for f in np.linspace(0,1,256)]],dtype='uint8'),aspect='auto')
axL.set_xticks([]); axL.set_yticks([])
axL.set_xlabel("colour response, cold to hot",fontsize=5.4,color=MUTED,labelpad=1)
gy,gx=np.mgrid[0:8,0:8].astype(float)
fld=(np.exp(-(((gx-5.2)**2+(gy-2.6)**2)/(2*1.15**2)))*.75
     +np.exp(-(((gx-2.1)**2+(gy-5.4)**2)/(2*1.6**2)))*.30
     +np.exp(-(((gx-.6)**2+(gy-1.2)**2)/(2*2.6**2)))*.10)
fld/=fld.max()
axA=fig.add_subplot(gs[1,0]); axA.imshow(fld,cmap='gray_r',interpolation='nearest')
axA.set_xticks(range(8)); axA.set_yticks(range(8)); axA.tick_params(labelsize=4.0,length=0,colors=MUTED)
axA.set_title("raw 8x8 field",fontsize=5.8,pad=2)
big=np.clip(ndimage.zoom(fld,32,order=3),0,1)
rgb=np.array([[ramp(v) for v in row] for row in big],dtype='uint8')
axB=fig.add_subplot(gs[1,1]); axB.imshow(rgb)
axB.set_xticks([]); axB.set_yticks([]); axB.set_title("bicubic + palette",fontsize=5.8,pad=2)
r,cc=np.unravel_index(np.argmax(fld),fld.shape)
thr=big>(big.mean()+big.std()); e=np.zeros_like(thr)
e[1:,:]|=thr[1:,:]&~thr[:-1,:]; e[:-1,:]|=thr[:-1,:]&~thr[1:,:]
e[:,1:]|=thr[:,1:]&~thr[:,:-1]; e[:,:-1]|=thr[:,:-1]&~thr[:,1:]
out=rgb.copy(); out[e]=(0,255,120)
axC=fig.add_subplot(gs[1,2]); axC.imshow(out)
axC.plot((cc+.5)*32-16,(r+.5)*32-16,marker='s',ms=7,mfc='none',mec=RED,mew=1.1)
axC.set_xticks([]); axC.set_yticks([]); axC.set_title("Otsu outline, hotspot",fontsize=5.8,pad=2)
save(fig,"col_detection.png")

print("done ->",OUT)
