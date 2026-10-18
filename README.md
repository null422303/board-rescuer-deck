# Thermal Vision — AMG8833 → VPS → web

An ESP32 with an **AMG8833 "Grid-EYE" 8×8 IR sensor** pushes frames over TLS to a VPS.
The VPS keeps **only the raw 8×8 temperature grid**, renders every image **server-side**,
and streams it to any browser at up to 30 fps. A phone camera can overlay the heat map on
the live view to hunt hot components; a vision AI names the component and finds a price on
Amazon.in / Flipkart.

```
ESP32 + AMG8833  --TLS POST (128 B/frame, 10 fps)-->  VPS :8090  --SSE (2 PNGs)--> any browser
                                                          |
                                                          +-- camera overlay (browser) --snap--> gallery + AI
```

Public URL: **https://thermal.144.202.52.34.nip.io/** · docs at **/docs**

---

## Layout

```
thermal/
├── esp32/
│   ├── amg_thermal_push.ino   # ← the one flashed (station mode, pushes to the VPS)
│   └── amg_thermal_sta.ino    # earlier station-mode sketch (reference)
├── vps/
│   └── thermal_server.py      # the whole server: ingest, render, SSE, UI, gallery, AI
├── assets/
│   ├── og.png                 # 1200×630 link-preview image
│   └── fx/*.gif               # pre-recorded demo loops (shown when the sensor is offline)
└── deploy/
    ├── thermal.service        # systemd unit (contains secrets — see below)
    └── caddy-thermal.conf     # Caddy site block (TLS + streaming)
```

---

## ESP32

**Hardware:** ESP32 (classic D0WD-V3) + AMG8833. Wiring: `SDA=21`, `SCL=22`, status LED `=2`.
Frames are sent as **128 bytes = 64 × int16 (°C × 100)**, little-endian, 10 fps
(AMG8833 hardware max). Fire-and-forget with a persistent TLS keep-alive connection and a
continuous response drain (the server's writes block if we don't read).

**Config** (`esp32/amg_thermal_push.ino`):

| What | Value |
|---|---|
| Wi-Fi SSID / pass | `Thermal` / `<WIFI_PASSWORD>` |
| Host | `thermal.144.202.52.34.nip.io` (port 443) |
| Token | `<THERMAL_TOKEN>` (must match the server `THERMAL_TOKEN`) |
| POST interval | `100 ms` |

**Flash:** open `esp32/amg_thermal_push.ino` in Arduino IDE, install the `Adafruit AMG88xx`
library, select the ESP32 board, upload on `/dev/ttyUSB0` (CP2102). It joins the `Thermal`
network and starts posting.

---

## VPS (Ubuntu 20.04, `144.202.52.34`)

Everything is a **single stdlib Python file** (`vps/thermal_server.py`) — only dependency is
**numpy**. It binds `127.0.0.1:8090`; Caddy fronts it with TLS and `flush_interval -1`
(no buffering, required for SSE).

**Install / update:**

```bash
scp vps/thermal_server.py   root@144.202.52.34:/root/
scp deploy/thermal.service  root@144.202.52.34:/root/           # first time only
scp assets/og.png           root@144.202.52.34:/opt/thermal/og.png
scp -r assets/fx            root@144.202.52.34:/opt/thermal/fx

ssh root@144.202.52.34 '
  install -m 0644 /root/thermal_server.py /opt/thermal/thermal_server.py
  install -m 0644 /root/thermal.service    /etc/systemd/system/thermal.service
  systemctl daemon-reload && systemctl restart thermal'
```

**Environment** (in `deploy/thermal.service`):

| Var | Meaning | Current |
|---|---|---|
| `THERMAL_BIND` / `THERMAL_PORT` | listen addr | `127.0.0.1` / `8090` |
| `THERMAL_TOKEN` | ingest auth (must match ESP32) | `1949ff…2b6124` |
| `THERMAL_PASS` | gallery passcode (snap/delete) | `<PASSCODE>` |
| `OPENROUTER_KEY` | AI key (server-side only) | `<OPENROUTER_KEY>` |
| `OR_VISION` / `OR_PRICE` | AI models | `z-ai/glm-5.3-flash` / `…:online` |
| `OR_AI` | `0` disables the AI job | `1` |
| `THERMAL_GALLERY` | photo dir | `/opt/thermal/gallery` |
| `THERMAL_GAL_MAX` / `THERMAL_GAL_DAYS` | retention (count / days) | `300` / `0` |
| `THERMAL_FX` / `THERMAL_OG` | demo gifs / preview image | `/opt/thermal/fx` / `…/og.png` |

> **Secrets live in `deploy/thermal.service`, `esp32/amg_thermal_push.ino` and this file.**
> Treat this folder as private.

**Change the passcode (no redeploy):**
```bash
ssh root@144.202.52.34
sed -i 's/^Environment=THERMAL_PASS=.*/Environment=THERMAL_PASS=YOURNEWPASS/' /etc/systemd/system/thermal.service
systemctl daemon-reload && systemctl restart thermal
```

---

## HTTP API

| Route | Purpose |
|---|---|
| `POST /api/ingest` | ESP32 pushes 128 bytes (token-gated) |
| `GET /api/stream` | SSE: `{seq,mn,mx,avg,efflo,effhi,rauto,rlo,rhi,k,lc,clip,thr,hot,hotat,g8,p8,raw,proc,…}` |
| `GET /api/latest` | one snapshot, no stream |
| `GET /api/astro?on=` · `/api/mode?m=` · `/api/thr?v=` · `/api/k?v=` · `/api/lc?v=` · `/api/clip?v=` · `/api/stack?v=` · `/api/range?auto=&lo=&hi=` | live controls (each bumps the sync `rev`) |
| `GET|POST /api/auth` | auth state / exchange passcode for the cookie |
| `POST /api/snap` | save a photo + start the AI job (**passcode**) |
| `GET /api/gallery` · `GET /g/<id>.jpg` | list / fetch photos (**public**) |
| `POST /api/gallery/del` | delete a photo (**passcode**) |
| `GET /fx/<combo>.gif` · `GET /og.png` | demo loops / link-preview image |

Access model: **viewing is public**, **snapping & deleting need the passcode** (server-checked,
HTTP-only cookie). See the in-app **/docs** page for the user-facing version.

---

## Processing pipeline (server-side, every frame)

1. Sigma-clipped rolling **stack** (`n` frames) — threshold `clip·1.4826·MAD`, floored at **0.15 °C**.
2. 180° flip + horizontal mirror (net vertical flip).
3. **Bicubic** upscale 8→256 + unsharp mask.
4. **asinh stretch** (`k`) with a k=0 guard.
5. **Additive local contrast** (`lc`, CLAHE-style).
6. **Ordered dither** (8×8 Bayer) → quantise to **32 levels**.
7. Contour lines = 20 %-black twins of each ramp colour; **Otsu outline** in green.
8. Pack to a 65-colour indexed **palette PNG**.

Auto colour window = **5th–95th percentile** of the frame (spike/flat-frame fallback), then
**glided** with an EMA so it never snaps blue/red. Manual window is seeded from AUTO when you
take over. The window, the Otsu threshold and the camera overlay all read the **same field**.

---

## Camera, gallery & AI

- **Camera & log** opens the rear camera; the heat map is warped on with a stored affine
  calibration (**Align** = 5 s re-nudge, saved per device in `localStorage`).
- **Snap** saves two JPEGs: the composited frame (gallery) and a **clean** frame
  (no heat map, just the hotspot box) which is what the AI sees.
- The VPS then: **vision** (`z-ai/glm-5.3-flash`) identifies the component under the hotspot,
  then a **web-search price** pass (`…:online`) finds it on **amazon.in / flipkart.com** in **₹**,
  requiring a real product page (`/dp/`, `/gp/product`, `/p/`, `/itm/`). Result is stored on the
  gallery item and shown under the photo with a `search ↗` link to verify.
- When the sensor is silent (>2.6 s) the panes play the matching **pre-recorded GIF**
  (`astro × mode`), the badge flips to **offline**, and a "SENSOR OFFLINE" label appears.

---

## Local notes

- The VPS is shared production (grindbux.com, aquasentinel, nagarai, QWEEN) — don't touch
  unrelated services. QWEEN needs `/root/.cache/ms-playwright`.
- Test the page with Playwright (headless chromium, `--no-sandbox`) at the public URL.
- `/docs` is served by the same page (auto-opens the docs) so CSS/content never drift.
