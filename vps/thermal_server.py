#!/usr/bin/env python3
"""
AMG8833 server: stores ONLY the raw 8x8, processes every frame server-side.

  POST /api/ingest      ESP32 pushes 128 bytes (64 x int16 degC x100)
  GET  /api/stream      SSE: {seq, mn, mx, avg, stack, astro, raw, proc}  (raw/proc = base64 PNG)
  GET  /api/astro?on=1  toggle the astro pipeline
  GET  /                UI (Raw | Processed, side by side)

Pipeline (all numpy, server side):
  stack(sigma-clipped rolling mean) -> 180 deg flip -> bicubic 8->256 (matrix)
  -> background removal -> asinh/gamma stretch -> unsharp mask
  -> palette + always-on outline (Otsu on the SAME normalised field, so colours
     and outline are in lock-step) -> palette PNG.

Auto-range stays per-frame (min->max, floor 0.5 C) and is the exact field the
overlay is computed from - that is what keeps them "hand in hand".
"""
import base64
import hashlib
import hmac
import json
import math
import os
import queue
import re
import struct
import urllib.parse
import urllib.request
import threading
import time
import zlib
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

PORT = int(os.environ.get("THERMAL_PORT", "8090"))
BIND = os.environ.get("THERMAL_BIND", "127.0.0.1")
TOKEN = os.environ.get("THERMAL_TOKEN", "")
# --- camera log: photos live here, gated by a passcode the SERVER checks ---
GAL_DIR = os.environ.get("THERMAL_GALLERY", "/opt/thermal/gallery")
GAL_INDEX = os.path.join(GAL_DIR, "index.json")
GAL_MAX = int(os.environ.get("THERMAL_GAL_MAX", "300"))
FX_DIR = os.environ.get("THERMAL_FX", "/opt/thermal/fx")
OG_IMG = os.environ.get("THERMAL_OG", "/opt/thermal/og.png")
GAL_DAYS = int(os.environ.get("THERMAL_GAL_DAYS", "0"))   # 0 = keep by count only
PASS = os.environ.get("THERMAL_PASS", "")
AUTH_TOKEN = hashlib.sha256((PASS + "|" + TOKEN).encode()).hexdigest()[:32]
MAX_BODY = 4096
MAX_SNAP = 8 * 1024 * 1024
# --- AI component ID + price lookup (OpenRouter) ---
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
OR_VISION = os.environ.get("OR_VISION", "z-ai/glm-5.3-flash")
OR_PRICE = os.environ.get("OR_PRICE", "z-ai/glm-5.3-flash:online")
OR_ON = os.environ.get("OR_AI", "1") == "1"
_gallock = threading.Lock()
N = 256            # render size
MAX_STACK = 30     # ring size; the slider picks how many of those to integrate

_lock = threading.Lock()
_subs = set()
_sublock = threading.Lock()
_buf = deque(maxlen=MAX_STACK)        # ONLY raw 8x8 frames
_astro = {"on": False, "k": 2.0, "lc": 1.0, "n": 12, "clip": 3.0}   # stretch, local contrast, stack, sigma-clip
_mode = {"m": "sharp"}                 # sharp | contour | blocks
_thr = {"v": 40.0}                     # hotspot alarm threshold (degC), shared
_range = {"auto": True, "lo": 30.0, "hi": 40.0}  # colour window: body-temp default (degC)
_state = {"seq": 0, "t": 0.0, "rev": 0}

# ---------------- colour LUT (thermal_viewer.py make_lut) ----------------
def _make_lut():
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        f = i / 255.0
        if f < 0.5:
            x = f * 2
            r, g, b = 0, x * 255, (1 - x) * 255
        else:
            x = (f - 0.5) * 2
            r, g, b = x * 255, (1 - x) * 255, 0
        lut[i] = [int(r), int(g), int(b)]
    return lut

LUT = _make_lut()

# Compact palette: ramp levels 0..QLEVELS-1, then outline / contour colours.
# Small indices also compress better in the PNG.
QLEVELS = 32
_RAMP = LUT[np.clip((np.arange(QLEVELS) * 256) // QLEVELS, 0, 255)].astype(np.uint8)
# contour lines = "black at 20% opacity" PRE-COMPOSITED onto each ramp colour.
# (a tRNS alpha would blend with the page background, not the heatmap under it)
_LINE = (_RAMP.astype(np.float64) * 0.8).astype(np.uint8)
PAL = np.vstack([_RAMP, _LINE, np.array([[0, 255, 120]], dtype=np.uint8)])
IDX_LINE = QLEVELS            # + level -> the 20%-black version of that colour
IDX_OUT = 2 * QLEVELS         # always-on outline
PLTE = PAL.tobytes()

def _cubic(x, a=-0.5):
    x = abs(x)
    if x < 1.0:
        return (a + 2) * x ** 3 - (a + 3) * x ** 2 + 1.0
    if x < 2.0:
        return a * x ** 3 - 5 * a * x ** 2 + 8 * a * x - 4 * a
    return 0.0

def _weights(n_out, n_in=8, a=-0.5):
    W = np.zeros((n_out, n_in), dtype=np.float64)
    for o in range(n_out):
        f = o * (n_in - 1) / (n_out - 1)
        i = int(math.floor(f))
        for k in range(-1, 3):
            idx = i + k
            if 0 <= idx < n_in:
                W[o, idx] += _cubic(f - idx, a)
    s = W.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    return W / s

W_SMOOTH = _weights(N, a=-0.5)               # Catmull-Rom
W_SHARP = _weights(N, a=-0.85)               # sharper kernel, crisper edges

# ---------------- tiny palette PNG encoder ----------------
def _chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))


def png_palette(idx):
    h, w = idx.shape
    # PNG "Up" filter: rows are near-identical in a smooth image -> huge saving
    d = np.empty((h, w), dtype=np.int16)
    d[0] = idx[0]
    d[1:] = idx[1:].astype(np.int16) - idx[:-1].astype(np.int16)
    raw = b"".join(b"\x02" + d[r].astype(np.uint8).tobytes() for r in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"PLTE", PLTE)
            + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b""))

# ---------------- helpers ----------------
def _blur3(x):
    y = x.copy()
    y[1:-1, :] = 0.25 * x[:-2, :] + 0.5 * x[1:-1, :] + 0.25 * x[2:, :]
    y[:, 1:-1] += 0.0
    z = y.copy()
    z[:, 1:-1] = 0.25 * y[:, :-2] + 0.5 * y[:, 1:-1] + 0.25 * y[:, 2:]
    return z

_BAYER8 = (np.array([[ 0, 32,  8, 40,  2, 34, 10, 42],
                     [48, 16, 56, 24, 50, 18, 58, 26],
                     [12, 44,  4, 36, 14, 46,  6, 38],
                     [60, 28, 52, 20, 62, 30, 54, 22],
                     [ 3, 35, 11, 43,  1, 33,  9, 41],
                     [51, 19, 59, 27, 49, 17, 57, 25],
                     [15, 47,  7, 39, 13, 45,  5, 37],
                     [63, 31, 55, 23, 61, 29, 53, 21]], dtype=np.float64) / 64.0 - 0.5)
DITHER = np.tile(_BAYER8, (N // 8, N // 8))       # +-0.5 of a palette step


def _boxblur(a, r):
    """Fast box blur via an integral image - used for local-mean (CLAHE-style)."""
    pad = np.pad(a, ((r, r), (r, r)), mode="edge")
    ii = np.pad(pad.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    H, W = a.shape
    k = 2 * r + 1
    return (ii[k:k + H, k:k + W] - ii[0:H, k:k + W]
            - ii[k:k + H, 0:W] + ii[0:H, 0:W]) / (k * k)


def _otsu(v):
    mn, mx = float(v.min()), float(v.max())
    if mx - mn < 0.4:
        return None
    nb = 256
    bi = ((v - mn) * ((nb - 1) / (mx - mn))).astype(np.int32)
    np.clip(bi, 0, nb - 1, out=bi)
    p = np.bincount(bi.ravel(), minlength=nb).astype(np.float64)
    total = float(v.size)
    idx = np.arange(nb, dtype=np.float64)
    wB = np.cumsum(p)
    wF = total - wB
    sum_all = float((p * idx).sum())
    sumB = np.cumsum(p * idx)
    with np.errstate(divide="ignore", invalid="ignore"):
        mB = np.where(wB > 0, sumB / wB, 0)
        mF = np.where(wF > 0, (sum_all - sumB) / wF, 0)
        between = wB * wF * (mB - mF) ** 2
    between[~np.isfinite(between)] = -1
    thr = int(np.argmax(between))
    lvl = mn + thr / (nb - 1) * (mx - mn)
    return min(max(lvl, mn + 0.05 * (mx - mn)), mx - 0.05 * (mx - mn))

def _outline_and_index(field, mode="sharp"):
    """Quantise to palette levels, add isotherm contours (optional), add the outline.
    Everything is computed on the SAME normalised field that is coloured, so the
    auto-range, the contours and the outline can never disagree."""
    field = np.clip(field + DITHER * (1.0 / QLEVELS), 0, 1)   # dither -> no banding
    lv = np.clip((field * QLEVELS).astype(np.int32), 0, QLEVELS - 1)
    idx = lv.astype(np.uint8)

    if mode == "contour":                      # iso-temperature lines separate blobs
        e = np.zeros(idx.shape, dtype=bool)
        e[1:, :] |= lv[1:, :] != lv[:-1, :]
        e[:-1, :] |= lv[:-1, :] != lv[1:, :]
        e[:, 1:] |= lv[:, 1:] != lv[:, :-1]
        e[:, :-1] |= lv[:, :-1] != lv[:, 1:]
        e[0, :] = e[-1, :] = e[:, 0] = e[:, -1] = False
        idx[e] = (IDX_LINE + lv[e]).astype(np.uint8)   # 20%-black line over the colour

    lvl = _otsu(field[::4, ::4])
    if lvl is not None:
        m = field >= lvl
        o = np.zeros_like(m)
        o[1:, :] |= m[1:, :] & ~m[:-1, :]
        o[:-1, :] |= m[:-1, :] & ~m[1:, :]
        o[:, 1:] |= m[:, 1:] & ~m[:, :-1]
        o[:, :-1] |= m[:, :-1] & ~m[:, 1:]
        o[0, :] = o[-1, :] = o[:, 0] = o[:, -1] = False
        idx[o] = IDX_OUT
    return idx, lvl

def _upscale(a8, mode="sharp"):
    if mode == "blocks":
        k = N // 8
        return np.repeat(np.repeat(a8, k, axis=0), k, axis=1)
    W = W_SHARP if mode in ("sharp", "contour") else W_SMOOTH
    big = W @ a8 @ W.T
    if mode in ("sharp", "contour"):
        big = big + 1.0 * (big - _blur3(big))     # unsharp: separate adjacent cells
    return big

def _render(raw8, proc_field, rlo, rhi, mode="sharp"):
    """raw8: 8x8 degC (already flipped). rlo/rhi = the shared colour window."""
    rng = max(rhi - rlo, 0.2)
    raw_n = np.clip((raw8 - rlo) / rng, 0, 1)
    raw_big = np.clip(_upscale(raw_n, mode), 0, 1)
    raw_idx, _ = _outline_and_index(raw_big, mode)

    if proc_field is None:
        return raw_idx, raw_idx
    p = np.clip(proc_field, 0, 1)
    big = np.clip(_upscale(p, mode), 0, 1)
    sharp = np.clip(big + 0.6 * (big - _blur3(big)), 0, 1)
    pidx, _ = _outline_and_index(sharp, mode)
    return raw_idx, pidx

# ---------------- astro pipeline (Milky-Way style) ----------------
def _astro_field(rlo, rhi):
    """Integrate -> normalise through the SHARED colour window -> asinh -> local contrast.
    Using the same window as the raw pane is what makes the colour range drive both."""
    n_use = max(1, min(int(_astro["n"]), len(_buf)))
    S = np.stack(list(_buf)[-n_use:])              # (n,8,8) raw degC
    med = np.median(S, axis=0)
    if n_use >= 4:
        diff = S - med
        gmad = float(np.median(np.abs(diff)))      # ONE global scale, not per-pixel
        thr = max(float(_astro["clip"]) * 1.4826 * gmad, 0.15)   # floor: never eat real signal
        A = np.where(np.abs(diff) < thr, S, med).mean(axis=0)
    else:
        A = S.mean(axis=0)                         # too few frames to clip safely
    n = np.clip((A - rlo) / max(rhi - rlo, 0.2), 0, 1)   # same window as raw
    k = _astro["k"]
    if k >= 0.01:                                  # global stretch (0 = linear)
        n = np.arcsinh(n * k) / math.asinh(k)
    lc = _astro["lc"]
    if lc > 0.01:                                  # CLAHE-style local contrast
        m = _boxblur(n, 3)
        d = n - m                                  # ADDITIVE: keeps the window's
        n = np.clip(n + lc * 3.0 * d, 0, 1)        # absolute mapping intact
    return n


def _gal_load():
    try:
        with open(GAL_INDEX) as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _gal_save(items):
    try:
        os.makedirs(GAL_DIR, exist_ok=True)
        tmp = GAL_INDEX + ".tmp"
        with open(tmp, "w") as f:
            json.dump(items, f)
        os.replace(tmp, GAL_INDEX)
    except Exception:
        pass


def _or_call(model, messages, max_tokens=600, timeout=90):
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + OPENROUTER_KEY,
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://thermal.144.202.52.34.nip.io",
                 "X-Title": "Thermal AMG8833"})
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            m = d["choices"][0]["message"]
            return m.get("content") or m.get("reasoning") or ""
        except Exception as e:
            last = e
            if attempt == 0:
                time.sleep(2)
    raise last


def _or_json(text):
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except Exception:
        return None


def _gal_update(item_id, patch):
    with _gallock:
        items = _gal_load()
        for it in items:
            if it.get("id") == item_id:
                it.update(patch)
                break
        _gal_save(items)


def _identify(item_id, blob, item):
    """Ask a vision model what component the hotspot is on, then price it online."""
    try:
        b64 = base64.b64encode(blob).decode()
        ctx = ""
        if item.get("mx") is not None:
            ctx = "Peak in the marked box is %.1f C (alarm at %.1f C)." % (item["mx"], item.get("thr", 40))
        vis = _or_call(OR_VISION, [{"role": "user", "content": [
            {"type": "text", "text": (
                "This is a clean camera photo of an electronics circuit board (no thermal overlay). A red "
                "rectangle marks the HOTTEST point. Identify the single electronic component the rectangle "
                "sits on, reading any printed marking. If no rectangle is visible, pick the component most "
                "likely to get hot. Reply with ONLY a JSON object, "
                "no prose, no markdown:\n"
                '{"component":"generic type e.g. electrolytic capacitor / MOSFET / voltage regulator / resistor / diode / microcontroller IC / connector",'
                '"part_number":"any printed marking readable, else empty",'
                '"package":"e.g. QFP / SOT-23 / TO-220 / 0805 / DIP-8, else empty",'
                '"description":"one short plain sentence","confidence":0-100}\n' + ctx)} ,
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}],
            max_tokens=500)
        info = _or_json(vis) or {"component": "unknown", "confidence": 0}
        comp = (info.get("component") or "").strip()
        if comp.lower() in ("", "unknown", "n/a", "none", "unclear"):
            info["price"] = {}
            info["status"] = "done"
            _gal_update(item_id, {"ai": info})
            return
        q = (info.get("part_number") or comp).strip()
        if info.get("package"):
            q += " " + info["package"]
        pr = _or_call(OR_PRICE, [{"role": "user", "content": (
            "Find ONE current listing to buy this electronic component in India, using live web search. "
            "Use ONLY amazon.in or flipkart.com - no other shops. "
            "Price a SINGLE unit. EXCLUDE dev boards, kits, multi-packs, bundles and accessories "
            "(unless the part itself is one). Prefer the BARE component. "
            "The url MUST be a real product page (Amazon: contains /dp/ or /gp/product ; "
            "Flipkart: contains /p/ or /itm/) - never a search, category or price-comparison page. "
            "Give the price in Indian rupees (INR, the \u20b9 symbol). "
            "If the exact part is genuinely not sold there, return an empty price. "
            "Component: " + q + ". " + (info.get("description") or "") + "\n"
            "Reply with ONLY a JSON object (no prose, no markdown):\n"
            '{"part":"exact part number","title":"the listing title as shown on the page",'
            '"price":"\u20b9x,xxx","vendor":"Amazon.in or Flipkart",'
            '"url":"https://www.amazon.in/.../dp/... or https://www.flipkart.com/.../p/itm..."}')}],
            max_tokens=700)
        pinfo = _or_json(pr) or {}
        u = (pinfo.get("url") or "").lower()
        is_prod = any(k in u for k in ("/dp/", "/gp/product", "/p/", "/itm/"))
        if not ((("amazon." in u) or ("flipkart." in u)) and is_prod):
            pinfo = {}                     # enforce: real Amazon.in / Flipkart product page
        info["price"] = pinfo
        info.pop("search", None)
        try:                               # always give a direct search link to verify
            if q:
                info["search"] = "https://www.amazon.in/s?k=" + urllib.parse.quote(q)
        except Exception:
            pass
        info["status"] = "done"
        _gal_update(item_id, {"ai": info})
    except Exception as e:
        _gal_update(item_id, {"ai": {"status": "error", "error": str(e)[:160]}})


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype, extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _chunk(self, d):
        self.wfile.write(b"%x\r\n" % len(d) + d + b"\r\n")
        self.wfile.flush()

    def _sse(self):
        q = queue.Queue(maxsize=2)
        with _sublock:
            _subs.add(q)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                try:
                    self._chunk(b"data: " + q.get(timeout=15) + b"\n\n")
                except queue.Empty:
                    self._chunk(b": ping\n\n")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sublock:
                _subs.discard(q)

    def do_HEAD(self):
        # link-preview crawlers (WhatsApp / Facebook) probe with HEAD first
        path, _, query = self.path.partition("?")
        if path in ("/og.png", "/preview.png") and os.path.isfile(OG_IMG):
            n = os.path.getsize(OG_IMG)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=86400")
        else:
            n = len(PAGE.encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(n))
        self.end_headers()

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/stream":
            return self._sse()
        if path == "/api/auth":
            return self._send(200, json.dumps({"authed": self._authed()}), "application/json")
        if path == "/api/gallery":
            # public on purpose: anyone with the link can VIEW the log
            return self._send(200, json.dumps({"items": _gal_load()}), "application/json")
        if path.startswith("/g/"):
            return self._serv_gallery(path[3:])
        if path.startswith("/fx/"):
            return self._serv_fx(path[4:])
        if path in ("/og.png", "/preview.png"):
            if os.path.isfile(OG_IMG):
                with open(OG_IMG, "rb") as f:
                    d = f.read()
                return self._send(200, d, "image/png", [("Cache-Control", "public, max-age=86400")])
            return self._send(404, "no", "text/plain")
        if path.rstrip("/") in ("/docs",):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/stack":
            try:
                v = int(float(query.split("v=")[1].split("&")[0]))
            except Exception:
                v = _astro["n"]
            v = max(1, min(MAX_STACK, v))
            with _lock:
                _astro["n"] = v
                _state["rev"] += 1
            return self._send(200, json.dumps({"stackn": v}), "application/json")
        if path == "/api/k":
            try:
                v = float(query.split("v=")[1].split("&")[0])
            except Exception:
                v = _astro["k"]
            v = max(0.0, min(8.0, v))
            with _lock:
                _astro["k"] = v
                _state["rev"] += 1
            return self._send(200, json.dumps({"k": v}), "application/json")
        if path == "/api/lc":
            try:
                v = float(query.split("v=")[1].split("&")[0])
            except Exception:
                v = _astro["lc"]
            v = max(0.0, min(3.0, v))
            with _lock:
                _astro["lc"] = v
                _state["rev"] += 1
            return self._send(200, json.dumps({"lc": v}), "application/json")
        if path == "/api/clip":
            try:
                v = float(query.split("v=")[1].split("&")[0])
            except Exception:
                v = _astro["clip"]
            v = max(0.3, min(10.0, v))
            with _lock:
                _astro["clip"] = v
                _state["rev"] += 1
            return self._send(200, json.dumps({"clip": v}), "application/json")
        if path == "/api/thr":
            try:
                v = float(query.split("v=")[1].split("&")[0])
            except Exception:
                v = _thr["v"]
            v = max(20.0, min(80.0, v))
            with _lock:
                _thr["v"] = v
                _state["rev"] += 1
            return self._send(200, json.dumps({"thr": v}), "application/json")
        if path == "/api/mode":
            m = "sharp"
            for k in ("contour", "blocks", "sharp"):
                if k in query:
                    m = k
                    break
            with _lock:
                _mode["m"] = m
                _state["rev"] += 1
            return self._send(200, json.dumps({"mode": m}), "application/json")
        if path == "/api/range":
            q = dict(p.split("=", 1) if "=" in p else (p, "") for p in query.split("&") if p)
            with _lock:
                if "auto" in q:
                    _range["auto"] = q["auto"] not in ("0", "false", "off")
                span = 0.5
                if "lo" in q:
                    lo = max(5.0, min(60.0, float(q["lo"])))
                    _range["lo"] = lo
                    if _range["hi"] < lo + span:          # never invert the window
                        _range["hi"] = min(60.0, lo + span)
                if "hi" in q:
                    hi = max(5.0, min(60.0, float(q["hi"])))
                    _range["hi"] = hi
                    if _range["lo"] > hi - span:
                        _range["lo"] = max(5.0, hi - span)
                _state["rev"] += 1
                out = dict(_range)
            return self._send(200, json.dumps(out), "application/json")
        if path == "/api/astro":
            on = "1" in query or "on=1" in query
            with _lock:
                _astro["on"] = on
                _state["rev"] += 1
            self._send(200, json.dumps({"astro": on}), "application/json")
            return
        if path == "/api/latest":
            with _lock:
                s = dict(_state)
            s.pop("raw", None); s.pop("proc", None)
            return self._send(200, json.dumps(s), "application/json")
        return self._send(200, PAGE, "text/html; charset=utf-8")

    def _read_body(self, cap=MAX_SNAP):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0 or n > cap:
            return b""
        return self.rfile.read(n)

    def _cookie(self, name):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def _authed(self):
        c = self._cookie("tauth")
        return bool(c) and hmac.compare_digest(c, AUTH_TOKEN)

    def _serv_fx(self, name):
        # pre-recorded demo GIFs shown when the sensor is silent
        if not re.match(r"^[a-z0-9_-]+\.gif$", name):
            return self._send(400, "no", "text/plain")
        fp = os.path.join(FX_DIR, name)
        if not os.path.isfile(fp):
            return self._send(404, "no", "text/plain")
        with open(fp, "rb") as f:
            d = f.read()
        return self._send(200, d, "image/gif", [("Cache-Control", "public, max-age=86400")])

    def _serv_gallery(self, name):
        # public on purpose: anyone with the link can VIEW the photos
        if not re.match(r"^[0-9]{6,20}\.jpg$", name):
            return self._send(400, "no", "text/plain")
        fp = os.path.join(GAL_DIR, name)
        if not os.path.isfile(fp):
            return self._send(404, "no", "text/plain")
        with open(fp, "rb") as f:
            d = f.read()
        return self._send(200, d, "image/jpeg", [("Cache-Control", "private, max-age=86400")])

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/auth":
            b = self._read_body(512)
            if not hmac.compare_digest(b.decode("utf-8", "ignore").strip(), PASS):
                time.sleep(0.4)                      # slow down guessing
                return self._send(403, json.dumps({"ok": False}), "application/json")
            return self._send(200, json.dumps({"ok": True}), "application/json",
                              [("Set-Cookie", "tauth=%s; Path=/; HttpOnly; SameSite=Lax; "
                                              "Max-Age=2592000" % AUTH_TOKEN)])
        if path == "/api/gallery/del":
            if not self._authed():
                return self._send(401, json.dumps({"ok": False}), "application/json")
            try:
                gid = json.loads(self._read_body(512)).get("id", "")
            except Exception:
                gid = ""
            items = _gal_load()
            keep = [x for x in items if x.get("id") != gid]
            if len(keep) != len(items):
                try:
                    os.remove(os.path.join(GAL_DIR, gid + ".jpg"))
                except OSError:
                    pass
                _gal_save(keep)
            return self._send(200, json.dumps({"ok": True, "items": keep}), "application/json")
        if path == "/api/snap":
            if not self._authed():
                return self._send(401, json.dumps({"ok": False}), "application/json")
            try:
                req = json.loads(self._read_body())
                img = req.get("img", "")
                meta = req.get("meta", {}) or {}
                b64 = img.split(",", 1)[1] if "," in img else ""
                blob = base64.b64decode(b64)
                cimg = req.get("clean", "") or ""
                cb64 = cimg.split(",", 1)[1] if "," in cimg else ""
                cblob = base64.b64decode(cb64) if cb64 else b""
                if not cblob.startswith(b"\xff\xd8"):
                    cblob = b""
            except Exception:
                return self._send(400, json.dumps({"ok": False}), "application/json")
            if not blob.startswith(b"\xff\xd8") or len(blob) > 6 * 1024 * 1024:
                return self._send(400, json.dumps({"ok": False}), "application/json")
            os.makedirs(GAL_DIR, exist_ok=True)
            gid = "%d" % int(time.time() * 1000)
            with open(os.path.join(GAL_DIR, gid + ".jpg"), "wb") as f:
                f.write(blob)
            with _lock:
                cur = {"mn": _state.get("mn"), "mx": _state.get("mx"),
                       "avg": _state.get("avg"), "thr": _thr["v"]}
            item = {"id": gid, "ts": round(time.time(), 1), "bytes": len(blob),
                    "mn": meta.get("mn", cur["mn"]), "mx": meta.get("mx", cur["mx"]),
                    "avg": meta.get("avg", cur["avg"]), "thr": cur["thr"],
                    "hot": bool((meta.get("mx") if meta.get("mx") is not None else (cur["mx"] or 0)) >= cur["thr"]),
                    "note": str(meta.get("note", ""))[:200]}
            items = _gal_load()
            items.append(item)
            while len(items) > GAL_MAX:                 # retention: oldest first
                old = items.pop(0)
                try:
                    os.remove(os.path.join(GAL_DIR, old["id"] + ".jpg"))
                except OSError:
                    pass
            if GAL_DAYS > 0:
                cut = time.time() - GAL_DAYS * 86400
                keep = [x for x in items if x.get("ts", 0) >= cut]
                for x in items:
                    if x not in keep:
                        try:
                            os.remove(os.path.join(GAL_DIR, x["id"] + ".jpg"))
                        except OSError:
                            pass
                items = keep
            if OPENROUTER_KEY and OR_ON:
                item["ai"] = {"status": "pending"}
            _gal_save(items)
            if item.get("ai"):
                threading.Thread(target=_identify, args=(gid, cblob or blob, dict(item)), daemon=True).start()
            return self._send(200, json.dumps({"ok": True, "item": item}), "application/json")
        if path != "/api/ingest":
            return self._send(404, "no", "text/plain")
        if self.headers.get("X-Auth-Token") != TOKEN:
            return self._send(403, "no", "text/plain")
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n != 128:
            return self._send(400, "no", "text/plain")
        raw = self.rfile.read(n)
        a = np.array(struct.unpack("<64h", raw), dtype=np.float64).reshape(8, 8) / 100.0
        a = a[::-1, ::-1]                       # 180 deg flip (sensor mounted upside down)
        a = a[:, ::-1]                          # + horizontal mirror  -> net vertical flip

        with _lock:
            _buf.append(a)                      # store ONLY the raw 8x8
            mn, mx = float(a.min()), float(a.max())
            astro_on = _astro["on"]
            mn_f, mx_f = float(a.min()), float(a.max())
            if _range["auto"]:
                # robust auto window: trim the top/bottom few % so one stray hot cell
                # or a glitchy/flat frame can't drag the window and wash the frame blue
                plo = float(np.percentile(a, 5.0))
                phi = float(np.percentile(a, 95.0))
                if phi - plo < 1.2:            # uniform scene or a lone spike
                    med = float(np.median(a))
                    rlo, rhi = med - 0.8, med + 1.7
                else:
                    rlo, rhi = plo, phi
                prev = _state.get("eff")
                if prev and (prev[1] - prev[0]) >= 0.3:
                    # glide the window instead of snapping -> no sudden blue/red flash
                    rlo = 0.7 * prev[0] + 0.3 * rlo
                    rhi = 0.7 * prev[1] + 0.3 * rhi
                if rhi - rlo < 0.5:
                    rhi = rlo + 0.5
            else:
                rlo = _range["lo"]; rhi = max(_range["hi"], _range["lo"] + 0.2)
            pf = _astro_field(rlo, rhi) if astro_on else None
            _state["used"] = max(1, min(int(_astro["n"]), len(_buf)))
            _state["eff"] = (round(rlo, 1), round(rhi, 1))
            raw_idx, proc_idx = _render(a, pf, rlo, rhi, _mode["m"])
            raw_png = base64.b64encode(png_palette(raw_idx)).decode()
            # astro off -> proc would be byte-identical to raw: send it once and let
            # the client reuse the same data URL (halves the payload)
            proc_png = None if pf is None else base64.b64encode(png_palette(proc_idx)).decode()
            _state["seq"] += 1
            _state["t"] = time.time()
            _state["mn"] = round(mn, 2)
            _state["mx"] = round(mx, 2)
            _state["avg"] = round(float(a.mean()), 2)
            with _sublock:
                viewers = len(_subs)
            payload = json.dumps({"seq": _state["seq"], "mn": round(mn, 2), "mx": round(mx, 2),
                                  "avg": round(float(a.mean()), 2), "astro": astro_on,
                                  "stack": _state.get("used", 0), "stackn": _astro["n"], "mode": _mode["m"],
                                  "viewers": viewers, "rev": _state["rev"],
                                  "rauto": _range["auto"], "rlo": _range["lo"], "rhi": _range["hi"],
                                  "efflo": _state.get("eff", (0, 0))[0], "effhi": _state.get("eff", (0, 0))[1],
                                  "k": _astro["k"], "lc": _astro["lc"], "clip": _astro["clip"],
                                  "thr": _thr["v"], "hot": bool(mx >= _thr["v"]),
                                  "hotat": [int(np.unravel_index(np.argmax(a), a.shape)[0]),
                                            int(np.unravel_index(np.argmax(a), a.shape)[1])],
                                  "g8": [int(round(float(v) * 100)) for v in a.ravel()],
                                  "p8": ([int(round(float(v) * 255)) for v in pf.ravel()]
                                         if pf is not None else None),
                                  "raw": raw_png, "proc": proc_png})
        data = payload.encode()
        with _sublock:
            subs = list(_subs)
        for q in subs:
            try:
                q.put_nowait(data)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(data)
                except Exception:
                    pass
        return self._send(200, "ok", "text/plain")


PAGE = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Thermal Vision &middot; AMG8833 Live Heat Map</title>
<meta name="description" content="Live 8x8 infrared heat map from an AMG8833 sensor: server-rendered thermal view, hotspot alarm, phone camera overlay and AI component ID.">
<meta name="theme-color" content="#07070d">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Thermal Vision">
<meta property="og:title" content="Thermal Vision &middot; AMG8833 Live Heat Map">
<meta property="og:description" content="Live 8x8 infrared heat map: server-rendered thermal view, hotspot alarm, camera overlay and AI component ID.">
<meta property="og:url" content="https://thermal.144.202.52.34.nip.io/">
<meta property="og:image" content="https://thermal.144.202.52.34.nip.io/og.png?v=2">
<meta property="og:image:secure_url" content="https://thermal.144.202.52.34.nip.io/og.png?v=2">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Thermal Vision &middot; AMG8833 Live Heat Map">
<meta name="twitter:description" content="Live 8x8 infrared heat map with hotspot alarm, camera overlay and AI component ID.">
<meta name="twitter:image" content="https://thermal.144.202.52.34.nip.io/og.png?v=2">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%2307070d'/><circle cx='16' cy='16' r='9' fill='url(%23g)'/><defs><radialGradient id='g'><stop offset='0' stop-color='%23ff4d6d'/><stop offset='.5' stop-color='%23ffcc00'/><stop offset='1' stop-color='%232b6cff'/></radialGradient></defs></svg>">
<style>
 :root{--bg:#07070d;--card:#111119;--line:#232333;--fg:#e9e9f2;--dim:#8b8ba6;--good:#3ddc97;--accent:#ff4d6d}
 *{box-sizing:border-box}
 body{margin:0;background:radial-gradient(1200px 700px at 50% -10%,#141427,var(--bg));
      color:var(--fg);font:15px/1.4 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial}
 html{scroll-behavior:smooth}
 ::selection{background:#ff4d6d55}
 .wrap{max-width:920px;margin:0 auto;padding:24px 18px 40px;overflow-x:clip}
 .brand{display:flex;align-items:center;gap:12px;min-width:0}
 .mark{width:36px;height:36px;border-radius:11px;flex:0 0 auto;
       background:radial-gradient(circle at 34% 32%,#ff4d6d,#ffcc00 48%,#2b6cff);
       box-shadow:0 8px 22px -8px #ff4d6d99,inset 0 1px 0 #ffffff33}
 .foot{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);
       color:var(--dim);font-size:12px;text-align:center;line-height:1.7}
 .foot a{color:var(--accent);text-decoration:none}
 .foot a:hover{text-decoration:underline}
 header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;flex-wrap:wrap}
 h1{margin:0;font-size:19px;font-weight:650}
 h1 small{display:block;font-weight:400;font-size:11.5px;color:var(--dim);margin-top:3px}
 .badges{display:flex;gap:8px;flex-wrap:wrap}
 .badge{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;color:var(--dim);
        background:#0e0e18;border:1px solid var(--line);border-radius:999px;padding:5px 11px;font-variant-numeric:tabular-nums}
 .dot{width:7px;height:7px;border-radius:50%;background:var(--dim)}
 .badge.live .dot{background:var(--good);animation:pulse 2s infinite}
 .badge.bad .dot{background:var(--accent)}
 @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(61,220,151,.45)}70%{box-shadow:0 0 0 8px rgba(61,220,151,0)}100%{box-shadow:0 0 0 0 rgba(61,220,151,0)}}
 .panes{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 @media(max-width:640px){.panes{grid-template-columns:1fr}}
 .pane{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:10px;
       box-shadow:0 20px 50px -26px #000,inset 0 1px 0 #ffffff0a}
 .pane h2{margin:2px 4px 8px;font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:var(--dim);font-weight:600}
 .imgwrap{position:relative;aspect-ratio:1;border-radius:10px;overflow:hidden;background:#000}
 .imgwrap img{position:absolute;inset:0;width:100%;height:100%;opacity:1}
 .bar{display:flex;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap}
 .seg{display:flex;gap:6px;background:#0e0e18;border:1px solid var(--line);padding:5px;border-radius:14px}
 .seg button{padding:7px 13px;font-size:12px;border-radius:10px;background:transparent;border:1px solid transparent}
 .seg button.on{background:#1d2a52;border-color:#4b6cff;color:#cfe0ff}
 .mini{padding:7px 12px;font-size:11px;letter-spacing:1px;border-radius:10px;background:#16162a;border:1px solid var(--line)}
 .mini.on{background:#14351f;border-color:#1fd18a;color:#8dffc0}
 .stagewrap{position:relative}
 .alarm{position:absolute;left:50%;top:14px;transform:translate(-50%,-14px);opacity:0;pointer-events:none;
        background:linear-gradient(180deg,#ff3b5c,#c81e3c);color:#fff;font-weight:700;font-size:13px;
        letter-spacing:.6px;padding:10px 20px;border-radius:999px;transition:.18s;z-index:40;
        box-shadow:0 10px 30px -6px #ff3b5c99}
 .alarm.on{opacity:1;transform:translate(-50%,0)}
 .offline{position:absolute;top:6px;left:50%;transform:translateX(-50%);display:none;z-index:39;
          background:#2a1b0e;border:1px solid #b5791f;color:#ffcc66;font-size:12px;font-weight:600;
          letter-spacing:.4px;padding:7px 14px;border-radius:999px;white-space:nowrap}
 .ctrl{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--card);border:1px solid var(--line);
       border-radius:14px;padding:12px 16px;font-size:13px;color:var(--dim);margin-top:12px;min-width:0}
 .ctrl>*{min-width:0}
 .ctrl input[type=range]{min-width:90px}
 .ctrl input[type=range]{-webkit-appearance:none;appearance:none;flex:1;height:4px;border-radius:3px;
       background:linear-gradient(90deg,#2b6cff,#ffcc00,#ff3b5c);outline:none}
 .ctrl input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;
       background:#fff;border:3px solid #0e0e18;box-shadow:0 2px 8px #000a;cursor:pointer}
 .ctrl b{color:var(--fg);font-variant-numeric:tabular-nums;min-width:60px;text-align:right}
 .toast{position:fixed;left:50%;top:18px;transform:translate(-50%,-16px);opacity:0;pointer-events:none;
        background:#1d2a52;border:1px solid #4b6cff;color:#cfe0ff;font-size:12.5px;font-weight:600;
        padding:9px 16px;border-radius:999px;transition:.2s;z-index:50;box-shadow:0 10px 30px -8px #000}
 .toast.on{opacity:1;transform:translate(-50%,0)}
 button{font:inherit;font-size:13px;font-weight:600;padding:11px 20px;border-radius:12px;border:1px solid var(--line);
        background:#16162a;color:var(--fg);cursor:pointer;transition:.15s}
 button:hover{border-color:#3a3a55}
 button.on{background:linear-gradient(180deg,#1fd18a,#12a06a);border-color:#1fd18a;color:#03130d}
 .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
 .chip{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:11px 13px}
 .chip span{display:block;font-size:10px;letter-spacing:1.3px;color:var(--dim);text-transform:uppercase}
 .chip b{font-size:19px;font-weight:600;font-variant-numeric:tabular-nums}
 .nav{display:flex;gap:8px;margin:4px 0 16px;flex-wrap:wrap}
 .nav button{padding:8px 14px;font-size:12px;letter-spacing:.5px}
 .nav button.on{background:var(--accent);border-color:var(--accent);color:#0b0b12}
 #docsov{display:none;position:fixed;inset:0;background:rgba(6,6,11,.985);z-index:120;
         overflow-y:auto;overflow-x:hidden;-webkit-overflow-scrolling:touch;padding:0 14px 80px}
 #docsov .doc{max-width:860px;margin:0 auto}
 #docsov h2{font-size:12.5px;letter-spacing:1.7px;text-transform:uppercase;color:var(--accent);
            margin:30px 0 8px;font-weight:700}
 #docsov h3{font-size:14.5px;margin:18px 0 5px}
 #docsov p{font-size:13.5px;line-height:1.65;margin:7px 0}
 #docsov ul{margin:7px 0;padding-left:20px}
 #docsov li{font-size:13px;line-height:1.6;color:var(--dim);margin:3px 0}
 #docsov li b,#docsov p b{color:var(--fg)}
 #docsov code{background:#16162a;border:1px solid var(--line);border-radius:6px;padding:1px 6px;
              font-size:12.5px;font-family:ui-monospace,Menlo,Consolas,monospace;color:#ffd7de;
              word-break:break-word;overflow-wrap:anywhere}
 #docsov pre{background:#0e0e18;border:1px solid var(--line);border-radius:11px;padding:12px 14px;
             white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#9fe8c4;
             font-family:ui-monospace,Menlo,Consolas,monospace}
 #docsov table{border-collapse:collapse;width:100%;margin:9px 0;font-size:12.5px}
 #docsov th,#docsov td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top;line-height:1.5;
                       word-break:break-word;overflow-wrap:anywhere}
 #docsov h2,#docsov h3,#docsov p,#docsov li{overflow-wrap:anywhere}
 @media(max-width:560px){
   #docsov{padding:0 11px 70px}
   #docstop{margin:0 -11px 12px;padding:11px 12px}
   #docsov th,#docsov td{padding:6px 7px}
   #docsov pre{padding:10px 11px}
   #docsov ul{padding-left:17px}
 }
 #docsov th{color:var(--dim);font-size:10.5px;letter-spacing:1px;text-transform:uppercase;background:#0e0e18}
 #docsov td b{color:var(--fg)}
 #docsov a{color:var(--accent)}
 #docstop{position:sticky;top:0;z-index:3;background:rgba(6,6,11,.99);border-bottom:1px solid var(--line);
          margin:0 -14px 14px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:12px}
 #docsov .doc{margin-top:0}
</style></head><body>
<div id="toast" class="toast"></div>
<div class="wrap">
  <header>
    <div class="brand">
      <span class="mark"></span>
      <h1>Thermal Vision<small>AMG8833 &middot; 8&times;8 IR grid &middot; live server-rendered heat map</small></h1>
    </div>
    <div class="badges">
      <span class="badge" id="conn"><i class="dot"></i><span id="connt">connecting</span></span>
      <span class="badge"><i class="dot" style="background:#4b6cff"></i><span id="fpst">-- fps</span></span>
      <span class="badge"><i class="dot" style="background:#8b8ba6"></i><span id="datarate">-- fps data</span></span>
      <span class="badge" id="livepill"><i class="dot" style="background:#ffcc00"></i><span id="viewers">-- watching</span></span>
    </div>
  </header>

  <nav class="nav">
    <button id="navcam">&#128247; Camera &amp; log</button>
    <button id="navdocs">&#128218; Docs</button>
  </nav>

  <div class="stagewrap">
    <div id="alarm" class="alarm">&#128680; HOTSPOT DETECTED</div>
    <div id="offline" class="offline">&#9888; SENSOR OFFLINE &middot; playing recorded demo</div>
  <div class="panes">
    <div class="pane"><h2>Raw (auto-ranged)</h2>
      <div class="imgwrap" id="rawwrap"><img alt=""></div></div>
    <div class="pane"><h2>Processed <span id="pmode">(astro off)</span></h2>
      <div class="imgwrap" id="procwrap"><img alt=""></div></div>
  </div>
  </div>

  <div class="bar">
    <button id="toggle">Start astro processing</button>
    <span style="font-size:12px;color:var(--dim)">render:</span>
    <div class="seg" id="modes">
      <button data-m="sharp" class="on">Sharp</button>
      <button data-m="contour">Contour</button>
      <button data-m="blocks">Blocks</button>
    </div>
  </div>

  <div class="ctrl">
    <label for="thr" style="white-space:nowrap">&#128293; Hotspot alarm</label>
    <input id="thr" type="range" min="20" max="80" step="0.5" value="40">
    <b id="thv">40.0&deg;C</b>
  </div>

  <div class="ctrl">
    <button id="autobtn" class="mini on">AUTO</button>
    <label for="rlo" style="white-space:nowrap">&#127752; Colour range</label>
    <input id="rlo" type="range" min="5" max="60" step="0.5" value="30">
    <b id="rlov">30.0&deg;</b>
    <input id="rhi" type="range" min="5" max="60" step="0.5" value="40">
    <b id="rhiv">40.0&deg;</b>
  </div>

  <div class="ctrl">
    <label for="stk" style="white-space:nowrap">&#9636; Stack</label>
    <input id="stk" type="range" min="1" max="30" step="1" value="12">
    <b id="stkv">12</b>
  </div>

  <div class="ctrl">
    <label for="ksl" style="white-space:nowrap">&#9728; Stretch</label>
    <input id="ksl" type="range" min="0" max="8" step="0.1" value="2">
    <b id="kv">2.0</b>
  </div>

  <div class="ctrl">
    <label for="lc" style="white-space:nowrap">&#128300; Local contrast</label>
    <input id="lc" type="range" min="0" max="3" step="0.05" value="0">
    <b id="lcv">0.00</b>
  </div>

  <div class="ctrl">
    <label for="clip" style="white-space:nowrap">&#9986; Sigma clip</label>
    <input id="clip" type="range" min="0.3" max="8" step="0.1" value="3">
    <b id="clipv">3.0&sigma;</b>
    <span style="font-size:11.5px;opacity:.65">low = smoother / can eat faint detail &middot; high = keeps more noise</span>
  </div>

  <div class="stats">
    <div class="chip"><span>Min</span><b id="mn">--</b></div>
    <div class="chip"><span>Max</span><b id="mx">--</b></div>
    <div class="chip"><span>Avg</span><b id="av">--</b></div>
    <div class="chip"><span>Window</span><b id="stkused">--</b></div>
  </div>

  <div class="bar" style="margin-top:20px">
    <button id="camopen">&#128247; Camera &amp; hotspot log</button>
    <span id="cammsg" style="font-size:12px;color:var(--dim)">view only &middot; passcode to snap</span>
  </div>

  <div id="passrow" class="ctrl" style="display:none">
    <label id="passlab" for="passin" style="white-space:nowrap">&#128274; Passcode</label>
    <input id="passin" type="password" autocomplete="current-password"
           style="flex:1;background:#0e0e18;border:1px solid var(--line);border-radius:10px;padding:9px 12px;color:var(--fg);font:inherit">
    <button id="passok">Unlock</button>
  </div>

  <div id="camshell" class="pane" style="display:none;margin-top:14px">
    <h2>Camera &middot; live thermal overlay</h2>
    <div id="camstage" style="position:relative;border-radius:12px;overflow:hidden;background:#000;touch-action:none;cursor:crosshair">
      <video id="cam" playsinline autoplay muted style="width:100%;display:block"></video>
      <canvas id="arc" style="position:absolute;inset:0;width:100%;height:100%"></canvas>
    </div>
    <div class="bar">
      <button id="shutter" class="on">&#9679; Snap to log</button>
      <button id="calbtn" class="mini">&#127919; Align</button>
      <button id="autoled" class="mini">&#128161; Auto from LEDs</button>
      <button id="camstop" class="mini">Close camera</button>
      <span id="camsx" style="font-size:12px;color:var(--dim)"></span>
    </div>
    <div id="calctrls" style="display:none">
      <div class="ctrl"><label style="white-space:nowrap">&#8596; Size</label>
        <input id="sz" type="range" min="0.15" max="2.6" step="0.01"><b id="szv">--</b></div>
      <div class="ctrl"><label style="white-space:nowrap">&#8635; Rotate</label>
        <input id="rot" type="range" min="-180" max="180" step="1"><b id="rotv">--</b></div>
      <div class="ctrl"><label style="white-space:nowrap">&#9788; Opacity</label>
        <input id="op" type="range" min="0" max="1" step="0.05"><b id="opv">--</b></div>
      <div class="ctrl">
        <button id="mirb" class="mini">&#8646; Mirror</button>
        <button id="calreset" class="mini">Reset</button>
        <span style="font-size:12px">Hold the sensor on something hot, then <b>drag</b> the heat over it. Saved per device.</span>
      </div>
    </div>
  </div>

  <div id="logpane" class="pane" style="margin-top:16px">
    <h2>Hotspot log <span id="galn" style="float:right;text-transform:none;letter-spacing:0">0 photos</span></h2>
    <div id="gal" style="display:flex;gap:9px;overflow-x:auto;-webkit-overflow-scrolling:touch;padding-bottom:8px;min-height:10px"></div>
    <div id="galempty" style="font-size:12.5px;color:var(--dim);padding:4px 2px">No photos yet &mdash; open <b>Camera &amp; log</b> and tap <b>Snap</b> to add one. Everyone can see this log.</div>
  </div>

  <footer class="foot">
    AMG8833 &middot; 8&times;8 IR &middot; ESP32 &rarr; VPS &rarr; browser<br>
    <a href="/docs">docs</a> &middot; server-side rendering &middot; only the raw 8&times;8 is stored
  </footer>
</div>

<div id="docsov"><div class="doc">
  <div id="docstop">
    <h1 style="margin:0;font-size:19px">Documentation<small style="display:block;font-weight:400;font-size:11px;color:var(--dim);margin-top:2px">AMG8833 thermal &middot; camera AR &middot; AI component ID</small></h1>
    <button id="docsclose">&#8592; Back to live</button>
  </div>

  <h2>1 &middot; What this is</h2>
  <p>An <b>ESP32</b> with an <b>AMG8833 &ldquo;Grid-EYE&rdquo;</b> 8&times;8 infrared sensor pushes frames over TLS to a VPS. The VPS keeps <b>only the raw 8&times;8 temperature grid</b>, renders every picture <b>server-side</b>, and streams it to any browser at up to 30&nbsp;fps. A phone camera can overlay the heat map on the live view to hunt hot components; a vision AI names the component and finds a cheap price.</p>
  <pre>ESP32 + AMG8833
   +-- TLS POST (128 B/frame) --> VPS :8090
        +-- SSE (2 PNGs) --> any browser
        +-- camera snap --> gallery + AI</pre>

  <h2>2 &middot; What is stored</h2>
  <ul>
    <li><b>Raw 8&times;8 frames only</b> &mdash; last 30, in RAM (<code>_buf</code>). The thermal stream is never written to disk.</li>
    <li><b>Nothing else</b> of the live feed is persisted. All colour, stacking, stretch, contour and outline happen fresh each frame.</li>
    <li><b>Gallery</b> &mdash; the composited phone JPEGs, their metadata and AI result, under <code>/opt/thermal/gallery/</code> (<code>index.json</code> + <code>&lt;id&gt;.jpg</code>), capped at <b>300</b>.</li>
  </ul>

  <h2>3 &middot; The processing pipeline</h2>
  <p>Applies to the <b>Processed</b> pane and, when astro is on, to the camera overlay:</p>
  <ul>
    <li>Sigma-clipped rolling mean <b>stack</b> (last N frames) &rarr; denoise.</li>
    <li>Display transform: <b>180&deg; flip + horizontal mirror</b> (net vertical flip).</li>
    <li><b>Bicubic upscale</b> 8&rarr;256, minus a background estimate.</li>
    <li><b>asinh stretch</b> (the <i>Stretch</i> slider) with a guard so k=0 is linear.</li>
    <li><b>Additive local contrast</b> (CLAHE-style).</li>
    <li><b>Ordered dither</b> (8&times;8 Bayer) to kill 32-level banding, then quantise to <b>32 levels</b>.</li>
    <li><b>Contour lines</b> drawn as 20%-black twins of each ramp colour (pre-composited, bandwidth-friendly).</li>
    <li><b>Otsu outline</b> of the hot shape, drawn in green (<code>[0,255,120]</code>), always on.</li>
    <li>Pack to an indexed <b>palette PNG</b> (65-colour palette, Up filter, zlib&nbsp;6).</li>
  </ul>
  <p>The colour window, the Otsu threshold and the overlay all read the <b>same normalised field</b>, so they never disagree.</p>

  <h2>4 &middot; Controls</h2>
  <table>
    <tr><th>Control</th><th>What it does</th><th>Default</th></tr>
    <tr><td><b>Start astro processing</b></td><td>Turns the whole Processed pipeline on/off. Off = raw, only scaled.</td><td>off</td></tr>
    <tr><td><b>Render &mdash; Sharp / Contour / Blocks</b></td><td>Upscale kernel + contour overlay. Sharp is the cleanest.</td><td>Sharp</td></tr>
    <tr><td><b>&#128293; Hotspot alarm</b></td><td>Any cell at/above this raises the red alarm banner + beep and marks snapped photos as hot.</td><td>40.0&nbsp;&deg;C</td></tr>
    <tr><td><b>&#9728; Stretch</b></td><td>asinh strength, 0 (linear) &rarr; 8 (max). Higher = more faint detail, until it saturates.</td><td>2.0</td></tr>
    <tr><td><b>&#128300; Local contrast</b></td><td>Additive CLAHE gain, 0&ndash;3. Brings out small differences across the frame.</td><td>1.0</td></tr>
    <tr><td><b>&#9986; Sigma clip</b></td><td>Stack outlier rejection strength (0.3&ndash;8&sigma;). Low = smoother but can eat faint real detail; high = keeps more noise. 0.15&nbsp;&deg;C floor always applies.</td><td>3.0</td></tr>
    <tr><td><b>&#9636; Stack</b></td><td>Frames averaged, 1&ndash;30. More = smoother but slower to react.</td><td>12</td></tr>
    <tr><td><b>&#127752; Colour range</b></td><td><b>AUTO</b> fits min&rarr;max every frame; manual sets the low/high &deg;C that map to blue/red. Never inverts (&ge;0.5&nbsp;&deg;C span).</td><td>AUTO 30&ndash;40</td></tr>
  </table>
  <p>Every control is <b>live-synced</b>: change it on one phone and every other viewer updates instantly (badge + toast).</p>

  <h2>5 &middot; Camera &amp; thermal overlay</h2>
  <ul>
    <li>Tap <b>&#128247; Camera &amp; log</b>. The rear camera becomes the viewfinder; the heat map is warped onto it.</li>
    <li><b>&#127919; Align</b> is the 5-second re-nudge: hold the sensor on something hot, drag the heat over it, tweak <b>Size / Rotate / Mirror</b>, then tap Align again. Saved in the phone's <code>localStorage</code>, so it survives reloads. <b>Reset</b> restores defaults.</li>
    <li>When astro is on the overlay colours from the <b>processed</b> field; when off it uses the raw 8&times;8 through the colour window.</li>
    <li>The hottest cell gets a box + its &deg;C; red if it crosses the hotspot alarm.</li>
  </ul>

  <h2>6 &middot; Gallery &amp; access</h2>
  <p><b>The Hotspot log sits on the main page and is public &mdash; anyone with this link can see every photo and its AI result.</b> Only <b>capturing</b> and <b>deleting</b> need the passcode. Tap any photo to open it full-size.</p>
  <table>
    <tr><th>Action</th><th>Public (no passcode)</th><th>With passcode</th></tr>
    <tr><td>Open the camera panel / live overlay</td><td>&#9989;</td><td>&#9989;</td></tr>
    <tr><td>View the gallery / a full photo</td><td>&#9989;</td><td>&#9989;</td></tr>
    <tr><td>Snap a new photo</td><td>&#10060; 401</td><td>&#9989;</td></tr>
    <tr><td>Delete a photo</td><td>&#10060; 401</td><td>&#9989;</td></tr>
  </table>
  <p>The passcode is checked <b>server-side</b> and sets an HTTP-only cookie (30 days). It is <b>not</b> in the page source. Old photos auto-delete once the gallery passes 300.</p>

  <h2>7 &middot; AI component ID &amp; price</h2>
  <p>On every snap the VPS runs a background job (key never touches the phone):</p>
  <pre>snap -> vision model : identify the component under the hotspot box
     -> price model  : live web search for the cheapest seller
     -> stored        : shown under the photo</pre>
  <ul>
    <li><b>Vision</b>: <code>z-ai/glm-5.3-flash</code>. <b>Price</b>: <code>z-ai/glm-5.3-flash:online</code> (web-search grounded).</li>
    <li>Returns component type, any read <b>part number</b>, package, a one-line description, a confidence %, and the cheapest price + seller + link &mdash; <b>Amazon.in or Flipkart only, in &#8377; (INR)</b>.</li>
    <li>If nothing is identified, it stops (no made-up prices).</li>
    <li>Prices are an <b>approximate estimate</b> from live web search (marked &asymp;), restricted to a real Amazon.in / Flipkart <b>product page</b> (single unit, no bundles). Tap <b>search&nearr;</b> to check the exact part yourself.</li>
    <li>Roughly <b>$0.01 per snap</b>. The card shows &ldquo;identifying part&hellip;&rdquo; until done (~10&nbsp;s).</li>
  </ul>

  <h2>8 &middot; HTTP API</h2>
  <table>
    <tr><th>Route</th><th>Purpose</th></tr>
    <tr><td><code>POST /api/ingest</code></td><td>ESP32 pushes 128 bytes = 64 &times; int16 (&deg;C&times;100). Token-gated.</td></tr>
    <tr><td><code>GET /api/stream</code></td><td>SSE: <code>{seq, mn, mx, avg, thr, stack, astro, g8, p8, hotat, raw, proc}</code> with base64 PNGs.</td></tr>
    <tr><td><code>GET /api/latest</code></td><td>One snapshot, no stream.</td></tr>
    <tr><td><code>GET /api/astro?on=</code> &middot; <code>/api/mode?m=</code> &middot; <code>/api/thr?v=</code> &middot; <code>/api/k?v=</code> &middot; <code>/api/lc?v=</code> &middot; <code>/api/stack?v=</code> &middot; <code>/api/range?auto=&amp;lo=&amp;hi=</code></td><td>Live controls; each bumps the sync revision.</td></tr>
    <tr><td><code>GET /api/auth</code> &middot; <code>POST /api/auth</code></td><td>Auth state / exchange passcode for the cookie.</td></tr>
    <tr><td><code>POST /api/snap</code></td><td>Save a photo + start the AI job. Needs passcode.</td></tr>
    <tr><td><code>GET /api/gallery</code> &middot; <code>GET /g/&lt;id&gt;.jpg</code></td><td>List / fetch photos. <b>Public.</b></td></tr>
    <tr><td><code>POST /api/gallery/del</code></td><td>Delete a photo. Needs passcode.</td></tr>
  </table>

  <h2>9 &middot; Ops &amp; security</h2>
  <ul>
    <li>Service: <code>systemctl restart thermal</code> (unit <code>/etc/systemd/system/thermal.service</code>), on <code>127.0.0.1:8090</code>, fronted by Caddy with streaming (no buffering).</li>
    <li>Env: <code>THERMAL_PASS</code> (passcode), <code>OPENROUTER_KEY</code>, <code>OR_VISION</code>/<code>OR_PRICE</code>, <code>OR_AI=0</code> to disable AI, <code>THERMAL_GAL_MAX</code>.</li>
    <li>The gallery is public by design &mdash; treat every photo as visible to anyone with the link.</li>
    <li>The AI key lives only in the systemd unit on the VPS; the browser never sees it.</li>
    <li>Only the passcode protects capture/delete &mdash; pick a long one.</li>
  </ul>

  <p style="margin-top:26px;color:var(--dim);font-size:12px">AMG8833 &middot; ESP32 &middot; endpoint <code>thermal.144.202.52.34.nip.io</code></p>
</div></div>

<script>
"use strict";
const $=id=>document.getElementById(id);
// ---- live sync: one shared state, every device mirrors it (server broadcasts) ----
let lastRev=-1, lastAstro=null, lastMode=null, lastThr=null, lastLc=null, lastStk=null, lastK=null, lastClip=null, pending=null, hotNow=false, dragThr=false, dragLc=false, dragStk=false, dragK=false, dragClip=false;
let actx=null;
function beep(){try{actx=actx||new(window.AudioContext||window.webkitAudioContext)();
  const o=actx.createOscillator(),g=actx.createGain();o.connect(g);g.connect(actx.destination);
  o.frequency.value=880;g.gain.setValueAtTime(.3,actx.currentTime);
  g.gain.exponentialRampToValueAtTime(.01,actx.currentTime+.3);o.start();o.stop(actx.currentTime+.3);}catch(e){}}
// ---- colour range: AUTO (per-frame min->max) or manual degC window ----
const rloEl=$('rlo'), rhiEl=$('rhi'); let rTimer=null, dragRange=false, lastEff=null;
function pushRange(){
  const lo=+rloEl.value, hi=+rhiEl.value;
  if(hi < lo+0.5){                       // keep lo < hi in the UI as well
    if(document.activeElement===rloEl){ rhiEl.value=(lo+0.5).toFixed(1); $('rhiv').textContent=(+rhiEl.value).toFixed(1)+'\u00B0'; }
    else { rloEl.value=(hi-0.5).toFixed(1); $('rlov').textContent=(+rloEl.value).toFixed(1)+'\u00B0'; }
  }
  dragRange=true; clearTimeout(rTimer);
  rTimer=setTimeout(async()=>{dragRange=false;pending={t:performance.now()};
    try{await fetch('/api/range?auto=0&lo='+rloEl.value+'&hi='+rhiEl.value,{cache:'no-store'});}catch(e){}},150);
}
function seedManual(movedLo){   // leaving AUTO -> start from the live window, no sudden shift
  if(!$('autobtn').classList.contains('on')||!lastEff)return;
  $('autobtn').classList.remove('on');
  if(movedLo){rhiEl.value=lastEff.hi.toFixed(1);$('rhiv').textContent=(+rhiEl.value).toFixed(1)+'\u00B0';}
  else{rloEl.value=lastEff.lo.toFixed(1);$('rlov').textContent=(+rloEl.value).toFixed(1)+'\u00B0';}
}
rloEl.addEventListener('input',()=>{seedManual(true);$('rlov').textContent=(+rloEl.value).toFixed(1)+'\u00B0';pushRange();});
rhiEl.addEventListener('input',()=>{seedManual(false);$('rhiv').textContent=(+rhiEl.value).toFixed(1)+'\u00B0';pushRange();});
$('autobtn').onclick=async()=>{
  const on=!$('autobtn').classList.contains('on');
  $('autobtn').classList.toggle('on',on);
  pending={t:performance.now()};
  try{await fetch('/api/range?auto='+(on?1:0),{cache:'no-store'});}catch(e){}
};
const stkEl=$('stk');let stkTimer=null;
stkEl.addEventListener('input',()=>{
  $('stkv').textContent=stkEl.value+' frames';
  dragStk=true;clearTimeout(stkTimer);
  stkTimer=setTimeout(async()=>{dragStk=false;pending={t:performance.now()};
    try{await fetch('/api/stack?v='+stkEl.value,{cache:'no-store'});}catch(e){}},140);
});
const kEl=$('ksl');let kTimer=null;
kEl.addEventListener('input',()=>{$('kv').textContent=(+kEl.value).toFixed(1);
  dragK=true;clearTimeout(kTimer);
  kTimer=setTimeout(async()=>{dragK=false;pending={t:performance.now()};
    try{await fetch('/api/k?v='+kEl.value,{cache:'no-store'});}catch(e){}},140);});
const lcEl=$('lc');let lcTimer=null;
lcEl.addEventListener('input',()=>{
  $('lcv').textContent=(+lcEl.value).toFixed(2);
  dragLc=true;clearTimeout(lcTimer);
  lcTimer=setTimeout(async()=>{dragLc=false;pending={t:performance.now()};
    try{await fetch('/api/lc?v='+lcEl.value,{cache:'no-store'});}catch(e){}},140);
});
const clipEl=$('clip');let clipTimer=null;
clipEl.addEventListener('input',()=>{
  $('clipv').textContent=(+clipEl.value).toFixed(1)+'\u03c3';
  dragClip=true;clearTimeout(clipTimer);
  clipTimer=setTimeout(async()=>{dragClip=false;pending={t:performance.now()};
    try{await fetch('/api/clip?v='+clipEl.value,{cache:'no-store'});}catch(e){}},140);
});
const thrEl=$('thr');let thrTimer=null;
thrEl.addEventListener('input',()=>{
  $('thv').textContent=(+thrEl.value).toFixed(1)+'\u00B0C';
  dragThr=true; clearTimeout(thrTimer);
  thrTimer=setTimeout(async()=>{dragThr=false;pending={t:performance.now()};
    try{await fetch('/api/thr?v='+thrEl.value,{cache:'no-store'});}catch(e){}},140);
});
function toast(msg){let t=$('toast');if(!t)return;t.textContent=msg;t.classList.add('on');
  clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('on'),2200);}
let lastSeq=-1,dc=0,ft=performance.now(),lastData=performance.now(),astro=false,curMode='sharp';
// ---- 30 fps frame application, no crossfade (frames swap directly) ----
const STEP=1000/30, OFFLINE_MS=2600;   // one threshold: demo GIF + header badge agree
let lastStep=0, viewTicks=0, pendRaw=null, pendProc=null;
const rawImg=document.querySelector('#rawwrap img'), procImg=document.querySelector('#procwrap img');
let fxCombo=null, fxOn=false;
function tick(now){
  requestAnimationFrame(tick);
  if(now-lastStep<STEP) return;          // cap application at 30 fps
  lastStep=now; viewTicks++;
  const stale=(now-lastData)>OFFLINE_MS;  // sensor silent -> play pre-recorded demo GIF
  if(stale){
    const c=(astro?'astro':'plain')+'-'+(curMode||'sharp');
    if(c!==fxCombo){fxCombo=c;rawImg.src='/fx/'+c+'.gif';procImg.src='/fx/'+c+'.gif';}
    if(!fxOn){fxOn=true;const o=$('offline');if(o)o.style.display='block';}
  } else {
    if(fxOn){fxOn=false;fxCombo=null;const o=$('offline');if(o)o.style.display='none';}
    if(pendRaw){ rawImg.src=pendRaw; procImg.src=pendProc; pendRaw=pendProc=null; }
  }
}
requestAnimationFrame(tick);
$('toggle').onclick=async()=>{
  astro=!astro;
  $('toggle').classList.toggle('on',astro);
  $('toggle').textContent=astro?'Stop astro processing':'Start astro processing';
  $('pmode').textContent=astro?'(astro on)':'(astro off)';
  pending={astro:astro,t:performance.now()};     // our own change -> no toast
  try{await fetch('/api/astro?on='+(astro?1:0),{cache:'no-store'});}catch(e){}
};

document.querySelectorAll('#modes button').forEach(b=>{
  b.onclick=async()=>{
    setMode(b.dataset.m);   // updates curMode now -> the offline demo GIF swaps immediately
    pending={mode:b.dataset.m,t:performance.now()};
    try{await fetch('/api/mode?m='+b.dataset.m,{cache:'no-store'});}catch(e){}
  };
});

function setMode(m){
  curMode=m;
  if(fxOn)fxCombo=null;   // combo changed -> swap the demo GIF on the next tick
  document.querySelectorAll('#modes button').forEach(x=>x.classList.toggle('on',x.dataset.m===m));
}

const es=new EventSource('/api/stream');
es.onerror=()=>{lastData=0;};   // connection dropped -> show the recorded demo
es.onmessage=e=>{try{
  const j=JSON.parse(e.data);
  if(j.seq===lastSeq)return;
  lastSeq=j.seq;dc++;lastData=performance.now();
  // feed the camera overlay: raw 8x8 + processed field + the window it was coloured with
  if(j.g8)tu_g8=j.g8;
  if(j.p8!==undefined)tu_p8=j.p8;
  if(j.efflo!=null)tu_lo=j.efflo;
  if(j.effhi!=null)tu_hi=j.effhi;
  tu_astro=j.astro; if(j.hotat)tu_hot=j.hotat;
  tu_mx=j.mx;tu_mn=j.mn;tu_av=j.avg;tu_thr=j.thr;
  const rawSrc='data:image/png;base64,'+j.raw;   // server-rendered, already flipped
  pendRaw=rawSrc;
  pendProc=j.proc?('data:image/png;base64,'+j.proc):rawSrc;   // reuse when astro off
  $('mn').textContent=j.mn.toFixed(1)+'\u00B0';
  $('mx').textContent=j.mx.toFixed(1)+'\u00B0';
  $('av').textContent=j.avg.toFixed(1)+'\u00B0';
  $('stkused').textContent=(j.efflo!=null?j.efflo.toFixed(1)+'\u2013'+j.effhi.toFixed(1)+'\u00B0':'--')+'  \u00B7  '+j.stack+'/'+j.stackn;
  // ---- live sync: any device can drive; the server is the single source of truth ----
  if(lastRev!==-1 && j.rev!==lastRev){
    const mine=(pending&&performance.now()-pending.t<2500);
    if(!mine){
      const what=[];
      if(lastAstro!==null&&j.astro!==lastAstro)what.push('astro '+(j.astro?'ON':'OFF'));
      if(lastMode!==null&&j.mode!==lastMode)what.push('render '+j.mode);
      if(lastThr!==null&&j.thr!==lastThr)what.push('alarm '+j.thr.toFixed(1)+'\u00B0C');
      if(lastLc!==null&&j.lc!==lastLc)what.push('local contrast '+j.lc.toFixed(2));
      if(lastClip!==null&&j.clip!=null&&j.clip!==lastClip)what.push('sigma clip '+j.clip.toFixed(1));
      if(lastStk!==null&&j.stackn!==lastStk)what.push('stack '+j.stackn);
      if(what.length)toast('Changed on another device \u00b7 '+what.join(' \u00b7 '));
    }
  }
  if(lastRev!==j.rev){lastRev=j.rev;lastAstro=j.astro;lastMode=j.mode;lastThr=j.thr;lastLc=j.lc;lastStk=j.stackn;lastK=j.k;lastClip=j.clip;}
  astro=j.astro;
  $('toggle').classList.toggle('on',astro);
  $('toggle').textContent=astro?'Stop astro processing':'Start astro processing';
  $('pmode').textContent=astro?'(astro on)':'(astro off)';
  if(j.mode)setMode(j.mode);
  if(j.thr!=null){if(!dragThr){thrEl.value=j.thr;$('thv').textContent=j.thr.toFixed(1)+'\u00B0C';}
    if(j.hot!==hotNow){hotNow=j.hot;$('alarm').classList.toggle('on',j.hot);
      if(j.hot)beep();}}
  if(j.stackn!=null&&!dragStk){stkEl.value=j.stackn;$('stkv').textContent=j.stackn+' frames';}
  if(j.rauto!=null){
    if(j.efflo!=null&&j.effhi!=null)lastEff={lo:j.efflo,hi:j.effhi};
    $('autobtn').classList.toggle('on',j.rauto);
    if(!dragRange){
      rloEl.value=j.rlo; rhiEl.value=j.rhi;
      $('rlov').textContent=(+j.rlo).toFixed(1)+'\u00B0';
      $('rhiv').textContent=(+j.rhi).toFixed(1)+'\u00B0';
    }
  }
  if(j.k!=null&&!dragK){kEl.value=j.k;$('kv').textContent=(+j.k).toFixed(1);}
  if(j.lc!=null&&!dragLc){lcEl.value=j.lc;$('lcv').textContent=(+j.lc).toFixed(2);}
  if(j.clip!=null&&!dragClip){clipEl.value=j.clip;$('clipv').textContent=(+j.clip).toFixed(1)+'\u03c3';}
  if(j.viewers!=null){$('viewers').textContent=j.viewers+' watching';
    $('livepill').className='badge'+(j.viewers>1?' live':'');}
}catch(_){}};

function loop(){
  const nw=performance.now();
  if(nw-ft>=1000){
    $('fpst').textContent=viewTicks+' fps view';
    viewTicks=0;
    $('datarate').textContent=dc+' fps data';
    const ok=(nw-lastData)<OFFLINE_MS;
    $('conn').className='badge'+(ok?' live':' bad');
    $('connt').textContent=ok?'live':'offline';
    dc=0;ft=nw;
  }
  requestAnimationFrame(loop);
}
loop();

/* ===== camera + live thermal overlay + hotspot log ===== */
var tu_g8=null,tu_p8=null,tu_lo=30,tu_hi=40,tu_astro=false,tu_hot=null,tu_mx=null,tu_mn=null,tu_av=null,tu_thr=40;
var RAMP=(function(){var a=[],n=32;for(var i=0;i<n;i++){var f=(i*8)/255;
  if(f<0.5)a.push([0,Math.round(f*2*255),Math.round((1-f*2)*255)]);
  else{var x=(f-0.5)*2;a.push([Math.round(x*255),Math.round((1-x)*255),0]);}}return a;})();
var tu_cal=null;
try{tu_cal=JSON.parse(localStorage.getItem('thermal_cal')||'null');}catch(e){tu_cal=null;}
if(!tu_cal||tu_cal.size==null)tu_cal={cx:0.5,cy:0.5,size:0.78,rot:0,mir:false,op:0.55};
var camOn=false,calMode=false,camStream=null,arRaf=0;
var camEl=$('cam'),arcEl=$('arc');
var tc=document.createElement('canvas');tc.width=tc.height=8;
var tctx=tc.getContext('2d');
var up=document.createElement('canvas');up.width=up.height=64;
var uctx=up.getContext('2d');uctx.imageSmoothingEnabled=true;
function tu_save(){try{localStorage.setItem('thermal_cal',JSON.stringify(tu_cal));}catch(e){}}
function tu_therm(){
  if(!tu_g8)return false;
  var img=tctx.createImageData(8,8),d=img.data,useP=(tu_astro&&tu_p8)?tu_p8:null;
  for(var i=0;i<64;i++){
    var f;
    if(useP)f=useP[i]/255;
    else{var rng=Math.max((tu_hi-tu_lo),0.2);f=(tu_g8[i]/100-tu_lo)/rng;}
    f=f<0?0:(f>1?1:f);
    var c=RAMP[Math.min(31,Math.round(f*31))];
    d[i*4]=c[0];d[i*4+1]=c[1];d[i*4+2]=c[2];d[i*4+3]=255;
  }
  tctx.putImageData(img,0,0);
  uctx.clearRect(0,0,64,64);
  uctx.drawImage(tc,0,0,8,8,0,0,64,64);
  return true;
}
function tu_aff(W,H){
  var s=tu_cal.size*W,r=tu_cal.rot*Math.PI/180,cs=Math.cos(r),sn=Math.sin(r);
  var a=s*cs,b=s*sn,c=-s*sn,d=s*cs;
  if(tu_cal.mir){a=-a;c=-c;}
  return {a:a,b:b,c:c,d:d,e:tu_cal.cx*W-(a*0.5+c*0.5),f:tu_cal.cy*H-(b*0.5+d*0.5)};
}
function tu_cell(row,col,W,H){
  var m=tu_aff(W,H),u=(col+0.5)/8,v=(row+0.5)/8;
  return [m.a*u+m.c*v+m.e, m.b*u+m.d*v+m.f];
}
function tu_draw(){
  if(!camOn)return;
  arRaf=requestAnimationFrame(tu_draw);
  var W=camEl.videoWidth,H=camEl.videoHeight;
  if(!W||!H)return;
  if(arcEl.width!==W||arcEl.height!==H){arcEl.width=W;arcEl.height=H;}
  var g=arcEl.getContext('2d');
  g.setTransform(1,0,0,1,0,0);
  g.clearRect(0,0,W,H);
  g.drawImage(camEl,0,0,W,H);
  if(!tu_therm())return;
  var m=tu_aff(W,H);
  g.save();
  g.globalAlpha=calMode?Math.max(tu_cal.op,0.8):tu_cal.op;
  g.imageSmoothingEnabled=true;
  g.setTransform(m.a,m.b,m.c,m.d,m.e,m.f);
  g.drawImage(up,0,0,1,1);
  g.restore();
  g.save();
  g.setTransform(1,0,0,1,0,0);
  if(calMode){
    g.strokeStyle='rgba(255,255,255,.85)';g.lineWidth=2;g.setLineDash([10,8]);
    g.strokeRect(0,0,W,H);g.setLineDash([]);
    var mid=tu_cell(3.5,3.5,W,H);
    g.beginPath();g.arc(mid[0],mid[1],Math.max(9,W*0.014),0,7);g.stroke();
  }
  var mhot=tu_hot;
  if(tu_cal.led&&tu_g8){var bh=tu_boardHot();mhot=[bh.r,bh.c];tu_mx=bh.v/100;}
  if(mhot&&mhot[0]!=null){
    // hottest-cell marker - shown in BOTH modes so you can align to it
    var p=tu_cell(mhot[0],mhot[1],W,H),hot=(tu_mx!=null&&tu_mx>=tu_thr);
    var box=Math.max(30,W*0.06);
    g.strokeStyle=hot?'#ff3b5c':'#ffcc00';g.lineWidth=Math.max(2,W*0.0035);
    g.strokeRect(p[0]-box/2,p[1]-box/2,box,box);
    if(calMode){g.beginPath();g.moveTo(p[0]-box*0.7,p[1]);g.lineTo(p[0]+box*0.7,p[1]);
                g.moveTo(p[0],p[1]-box*0.7);g.lineTo(p[0],p[1]+box*0.7);g.stroke();}
    g.font='bold '+Math.round(W*0.028)+'px ui-sans-serif,system-ui,Segoe UI,Roboto';
    g.textAlign='center';g.textBaseline='bottom';
    g.fillStyle=hot?'#ff3b5c':'#ffcc00';
    g.fillText((tu_mx!=null?tu_mx.toFixed(1):'')+'\u00B0C',p[0],p[1]-box/2-6);
  }
  g.restore();
}
var tu_authed=false,tu_pending=null,tu_pendingId=null;
async function tu_checkAuth(){
  try{var j=await (await fetch('/api/auth',{cache:'no-store'})).json();tu_authed=!!(j&&j.authed);}catch(e){}
  $('cammsg').textContent=tu_authed?'unlocked \u00b7 you can snap':'view only \u00b7 passcode to snap';
  tu_syncDels();
}
function tu_syncDels(){
  // delete buttons only exist for signed-in users
  var d=$('gal').querySelectorAll('.gdel');
  for(var i=0;i<d.length;i++)d[i].style.display=tu_authed?'block':'none';
}
function tu_needPass(what,id){
  tu_pending=what;tu_pendingId=id||null;
  $('passlab').textContent=what==='snap'?'\ud83d\udd12 Passcode to save':(what==='del'?'\ud83d\udd12 Passcode to delete':'\ud83d\udd12 Passcode');
  $('passrow').style.display='flex';$('passin').focus();
}
async function tu_openCam(){
  $('passrow').style.display='none';
  $('camshell').style.display='block';
  tu_checkAuth();
  try{
    camStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:960}},audio:false});
  }catch(e){$('camsx').textContent='camera blocked: '+e.name;return;}
  camEl.srcObject=camStream;
  try{await camEl.play();}catch(e){}
  camOn=true;tu_syncCtrls();
  if(!arRaf)tu_draw();
  tu_loadGal();
}
function tu_closeCam(){
  camOn=false;
  if(arRaf){cancelAnimationFrame(arRaf);arRaf=0;}
  if(camStream){camStream.getTracks().forEach(function(t){t.stop();});camStream=null;}
  camEl.srcObject=null;
  $('camshell').style.display='none';
}
function tu_syncCtrls(){
  $('sz').value=tu_cal.size;$('szv').textContent=tu_cal.size.toFixed(2);
  $('rot').value=tu_cal.rot;$('rotv').textContent=tu_cal.rot+'\u00B0';
  $('op').value=tu_cal.op;$('opv').textContent=tu_cal.op.toFixed(2);
  $('mirb').classList.toggle('on',!!tu_cal.mir);
  $('calctrls').style.display=calMode?'block':'none';
  $('calbtn').classList.toggle('on',calMode);
}
$('camopen').onclick=function(){tu_openCam();};
async function tu_trypass(){
  var v=$('passin').value;$('passin').value='';
  var r=null;try{r=await fetch('/api/auth',{method:'POST',body:v});}catch(e){}
  if(r&&r.ok){
    tu_authed=true;$('passrow').style.display='none';$('passin').style.borderColor='';
    $('cammsg').textContent='unlocked \u00b7 you can snap';tu_syncDels();
    var p=tu_pending,pd=tu_pendingId;tu_pending=null;tu_pendingId=null;
    if(p==='snap')tu_doSnap();else if(p==='del'&&pd)tu_del(pd);
  }else{$('passlab').textContent='\ud83d\udd12 Wrong passcode \u2014 try again';$('passin').style.borderColor='#ff4d6d';}
}
$('passok').onclick=tu_trypass;
$('passin').addEventListener('keydown',function(e){if(e.key==='Enter')tu_trypass();});
$('camstop').onclick=tu_closeCam;
$('calbtn').onclick=function(){calMode=!calMode;tu_syncCtrls();};
$('sz').addEventListener('input',function(){$('szv').textContent=(+this.value).toFixed(2);tu_cal.size=+this.value;tu_save();});
$('rot').addEventListener('input',function(){$('rotv').textContent=this.value+'\u00B0';tu_cal.rot=+this.value;tu_save();});
$('op').addEventListener('input',function(){$('opv').textContent=(+this.value).toFixed(2);tu_cal.op=+this.value;tu_save();});
$('mirb').onclick=function(){tu_cal.mir=!tu_cal.mir;tu_syncCtrls();tu_save();};
$('calreset').onclick=function(){tu_cal={cx:0.5,cy:0.5,size:0.78,rot:0,mir:false,op:0.55,led:false};tu_syncCtrls();tu_save();};
/* drag to nudge: only while Align is on, so a stray touch can't move it */
(function(){
  var st=null;
  $('camstage').addEventListener('pointerdown',function(e){
    if(!calMode)return;var r=e.currentTarget.getBoundingClientRect();
    st={x:e.clientX,y:e.clientY,w:r.width,h:r.height};
    try{e.currentTarget.setPointerCapture(e.pointerId);}catch(_){}});
  $('camstage').addEventListener('pointermove',function(e){
    if(!st)return;
    tu_cal.cx+=(e.clientX-st.x)/st.w;tu_cal.cy+=(e.clientY-st.y)/st.h;
    tu_cal.cx=Math.max(-0.6,Math.min(1.6,tu_cal.cx));
    tu_cal.cy=Math.max(-0.6,Math.min(1.6,tu_cal.cy));
    st.x=e.clientX;st.y=e.clientY;tu_save();
  });
  ['pointerup','pointercancel'].forEach(function(k){$('camstage').addEventListener(k,function(){st=null;});});
})();
$('shutter').onclick=function(){
  if(!camOn){$('camsx').textContent='open the camera first';return;}
  if(!tu_authed){tu_needPass('snap');return;}
  tu_doSnap();
};
/* Auto-calibration from two lamps.
   One lamp sits at the TOP-RIGHT of the view and one at the BOTTOM-LEFT, so each
   is looked for inside its own corner of the grid. They are deliberately NOT
   taken as "the two hottest cells overall": the hottest cell elsewhere belongs
   to the board under test, and that unknown third point is what we want the
   mapping to locate. */
function tu_hotIn(r0,r1,c0,c1){
  var best=-1e9,br=0,bc=0;
  for(var r=r0;r<=r1;r++)for(var c=c0;c<=c1;c++){
    var v=tu_g8[r*8+c]; if(v>best){best=v;br=r;bc=c;}
  }
  return {r:br,c:bc,v:best};
}
/* hottest cell that is NOT one of the two lamps */
function tu_boardHot(){
  var best=-1e9,br=0,bc=0;
  for(var r=0;r<8;r++)for(var c=0;c<8;c++){
    if((r<=2&&c>=5)||(r>=5&&c<=2))continue;
    var v=tu_g8[r*8+c]; if(v>best){best=v;br=r;bc=c;}
  }
  return {r:br,c:bc,v:best};
}
async function tu_autoLED(){
  if(!camOn){$('camsx').textContent='open the camera first';return;}
  var W=camEl.videoWidth,H=camEl.videoHeight;
  if(!W||!H){$('camsx').textContent='no video yet';return;}
  if(!tu_g8){$('camsx').textContent='no thermal frame yet';return;}

  /* camera: the two brightest, well-separated spots */
  var sw=160, sh=Math.max(1,Math.round(160*H/W));
  var cnv=document.createElement('canvas');cnv.width=sw;cnv.height=sh;
  var g=cnv.getContext('2d');g.drawImage(camEl,0,0,sw,sh);
  var px=g.getImageData(0,0,sw,sh).data, lum=new Float32Array(sw*sh);
  for(var i=0;i<sw*sh;i++){var o=i*4;lum[i]=0.299*px[o]+0.587*px[o+1]+0.114*px[o+2];}
  var i1=0,b1=-1;
  for(i=0;i<lum.length;i++)if(lum[i]>b1){b1=lum[i];i1=i;}
  var x1=i1%sw,y1=(i1/sw)|0, minD=Math.min(sw,sh)*0.30;
  var i2=-1,b2=-1;
  for(var y=0;y<sh;y++)for(var x=0;x<sw;x++){
    var dx=x-x1,dy=y-y1;
    if(Math.sqrt(dx*dx+dy*dy)<minD)continue;
    var v=lum[y*sw+x]; if(v>b2){b2=v;i2=y*sw+x;}
  }
  if(i2<0||b1<170||b2<170){
    $('camsx').textContent='lamps not visible: need two bright spots';return;
  }
  var C1=[x1*W/sw, y1*H/sh], C2=[(i2%sw)*W/sw, ((i2/sw)|0)*H/sh];
  if((C1[0]-C1[1])<(C2[0]-C2[1])){var t=C1;C1=C2;C2=t;}   // C1 = top-right

  /* thermal: one lamp per corner region */
  var TR=tu_hotIn(0,2,5,7), BL=tu_hotIn(5,7,0,2);
  var P1=[(TR.c+0.5)/8,(TR.r+0.5)/8], P2=[(BL.c+0.5)/8,(BL.r+0.5)/8];

  /* similarity from the two lamp pairs: scale, rotation, offset */
  var dv=[P2[0]-P1[0],P2[1]-P1[1]], dw=[C2[0]-C1[0],C2[1]-C1[1]];
  var L=Math.hypot(dv[0],dv[1]), Lp=Math.hypot(dw[0],dw[1]);
  if(L<0.05||Lp<20){$('camsx').textContent='lamps too close together';return;}
  var s=Lp/L, th=Math.atan2(dw[1],dw[0])-Math.atan2(dv[1],dv[0]);
  var cs=Math.cos(th), sn=Math.sin(th);
  var a=s*cs,bb=s*sn,c=-s*sn,d=s*cs;
  var e=C1[0]-(a*P1[0]+c*P1[1]);
  var f=C1[1]-(bb*P1[0]+d*P1[1]);
  tu_cal.size=s/W; tu_cal.rot=th*180/Math.PI; tu_cal.mir=false;
  tu_cal.cx=(e+(a+c)/2)/W; tu_cal.cy=(f+(bb+d)/2)/H;
  tu_cal.led=true;                       // marker now means "board fault, not a lamp"
  tu_syncCtrls();tu_save();

  /* report the third, unknown point */
  var bh=tu_boardHot();
  $('camsx').textContent='aligned from 2 lamps \u00b7 board hotspot '
    + (bh.v/100).toFixed(1) + '\u00b0C';
}
$('autoled').onclick=tu_autoLED;
function tu_cleanShot(){
  // plain camera frame + the hotspot box only (NO heat map) so the AI can see the part
  var W=camEl.videoWidth,H=camEl.videoHeight;
  if(!W||!H)return null;
  var c=document.createElement('canvas');c.width=W;c.height=H;
  var g=c.getContext('2d');
  g.drawImage(camEl,0,0,W,H);
  var mhot=tu_hot;
  if(tu_cal.led&&tu_g8){var bh=tu_boardHot();mhot=[bh.r,bh.c];tu_mx=bh.v/100;}
  if(mhot&&mhot[0]!=null){
    var p=tu_cell(mhot[0],mhot[1],W,H),box=Math.max(34,W*0.07);
    g.strokeStyle='#ff3b5c';g.lineWidth=Math.max(4,W*0.006);
    g.strokeRect(p[0]-box/2,p[1]-box/2,box,box);
    g.font='bold '+Math.round(W*0.03)+'px ui-sans-serif,system-ui';
    g.textAlign='center';g.textBaseline='bottom';g.fillStyle='#ff3b5c';
    g.fillText((tu_mx!=null?tu_mx.toFixed(1):'')+'\u00B0C',p[0],p[1]-box/2-8);
  }
  try{return c.toDataURL('image/jpeg',0.85);}catch(e){return null;}
}
async function tu_doSnap(){
  var url;try{url=arcEl.toDataURL('image/jpeg',0.82);}catch(e){return;}
  var clean=tu_cleanShot();
  $('shutter').textContent='saving\u2026';$('shutter').disabled=true;
  try{
    var r=await fetch('/api/snap',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({img:url,clean:clean,meta:{mn:tu_mn,mx:tu_mx,avg:tu_av},cal:tu_cal})});
    var j=await r.json();
    if(r.status===401){$('shutter').textContent='\u25CF Snap to log';$('shutter').disabled=false;tu_authed=false;tu_needPass('snap');return;}
    $('camsx').textContent=j&&j.ok?'saved':'save failed';
    if(j&&j.ok){tu_addGal(j.item,true);if(j.item&&j.item.ai)tu_pollAI();
      var e=$('galempty');if(e)e.style.display='none';
      var n=$('galn');if(n){var c=$('gal').children.length;n.textContent=c+(c===1?' photo':' photos');}}
  }catch(e){$('camsx').textContent='save failed';}
  $('shutter').textContent='\u25CF Snap to log';$('shutter').disabled=false;
}
async function tu_del(id){
  try{await fetch('/api/gallery/del',{method:'POST',body:JSON.stringify({id:id})});}catch(e){}
  var el=$('gal').querySelector('[data-id="'+id+'"]');if(el)el.remove();
}
function tu_esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function tu_fillAI(el,it){
  var a=it&&it.ai;
  if(!a){el.textContent='';return;}
  if(a.status==='pending'){el.innerHTML='<i>identifying part\u2026</i>';return;}
  if(a.status==='error'){el.textContent='ai unavailable';return;}
  var h='';
  if(a.component)h+='<b style="color:var(--fg)">'+tu_esc(a.component)+'</b>';
  if(a.confidence)h+=' <span style="opacity:.7">'+a.confidence+'%</span>';
  if(a.part_number)h+='<br><span>'+tu_esc(a.part_number)+'</span>';
  if(a.package)h+=' <span style="opacity:.7">'+tu_esc(a.package)+'</span>';
  var p=a.price||{};
  if(p.price)h+='<br><span style="color:#7dff9b">\u2248 '+tu_esc(p.price)+'</span>'+(p.vendor?' \u00b7 '+tu_esc(p.vendor):'');
  if(p.url&&/^https?:/i.test(p.url))h+=' <a href="'+tu_esc(p.url)+'" target="_blank" rel="noopener" style="color:var(--accent)">buy\u2197</a>';
  if(a.search&&/^https?:/i.test(a.search))h+=' <a href="'+tu_esc(a.search)+'" target="_blank" rel="noopener" style="color:var(--accent);opacity:.85">search\u2197</a>';
  if(p.title)h+='<br><span style="opacity:.55">'+tu_esc(p.title)+'</span>';
  if(a.description)h+='<br><span style="opacity:.65">'+tu_esc(a.description)+'</span>';
  el.innerHTML=h||'<i>no match</i>';
}
function tu_addGal(it,prepend){
  var box=$('gal'),el=document.createElement('div');
  el.dataset.id=it.id;
  el.style.cssText='flex:0 0 auto;width:158px;background:#0e0e18;border:1px solid var(--line);border-radius:11px;padding:6px;';
  var im=document.createElement('img');
  im.src='/g/'+it.id+'.jpg';im.loading='lazy';
  im.style.cssText='width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:7px;display:block;background:#000;cursor:zoom-in';
  im.onclick=function(){window.open('/g/'+it.id+'.jpg','_blank');};
  var cap=document.createElement('div');
  cap.style.cssText='font-size:10.5px;color:var(--dim);margin-top:4px;line-height:1.3';
  var t=new Date((it.ts||0)*1000);
  cap.textContent=(it.mx!=null?it.mx.toFixed(1)+'\u00B0':'--')+' \u00b7 '+t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  if(it.hot)cap.style.color='#ff6b83';
  var ai=document.createElement('div');
  ai.className='aibox';
  ai.style.cssText='font-size:10.5px;color:var(--dim);margin-top:5px;border-top:1px solid var(--line);padding-top:5px;line-height:1.4';
  tu_fillAI(ai,it);
  var del=document.createElement('button');
  del.textContent='\u2715';del.className='mini gdel';
  del.style.cssText='margin-top:5px;width:100%;padding:3px;font-size:10px';
  del.style.display=tu_authed?'block':'none';
  del.onclick=function(){tu_del(it.id);};
  el.appendChild(im);el.appendChild(cap);el.appendChild(ai);el.appendChild(del);
  if(prepend&&box.firstChild)box.insertBefore(el,box.firstChild);else box.appendChild(el);
}
var tu_pollT=0,tu_pollN=0;
function tu_pollAI(){
  if(tu_pollT)return;
  tu_pollN=0;
  tu_pollT=setInterval(async function(){
    tu_pollN++;
    if(tu_pollN>30){clearInterval(tu_pollT);tu_pollT=0;return;}
    try{
      var j=await (await fetch('/api/gallery',{cache:'no-store'})).json(),left=0;
      (j.items||[]).forEach(function(it){
        if(it.ai&&it.ai.status==='pending')left++;
        var el=$('gal').querySelector('[data-id="'+it.id+'"] .aibox');
        if(el&&it.ai&&it.ai.status!=='pending')tu_fillAI(el,it);
      });
      if(!left){clearInterval(tu_pollT);tu_pollT=0;}
    }catch(e){}
  },4000);
}
async function tu_loadGal(){
  try{
    var r=await fetch('/api/gallery',{cache:'no-store'});
    if(!r.ok)return;var j=await r.json(),box=$('gal'),items=j.items||[];
    box.innerHTML='';items.slice().reverse().forEach(function(it){tu_addGal(it,false);});
    var n=$('galn');if(n)n.textContent=items.length+(items.length===1?' photo':' photos');
    var e=$('galempty');if(e)e.style.display=items.length?'none':'block';
    if(items.some(function(it){return it.ai&&it.ai.status==='pending';}))tu_pollAI();
  }catch(e){}
}
function tu_isDocs(){return location.pathname.replace(/\/+$/,'')==='/docs';}
function tu_openDocs(){$('docsov').style.display='block';document.body.style.overflow='hidden';$('docsov').scrollTop=0;}
function tu_closeDocs(){
  if(tu_isDocs()){location.href='/';}
  else{$('docsov').style.display='none';document.body.style.overflow='';}
}
function tu_gotoDocs(){if(!tu_isDocs())history.pushState(null,'','/docs');tu_openDocs();}
$('navdocs').onclick=tu_gotoDocs;
$('docsclose').onclick=tu_closeDocs;
$('navcam').onclick=function(){if(tu_isDocs()){location.href='/#cam';return;}tu_openCam();$('camshell').scrollIntoView({behavior:'smooth',block:'start'});};
window.addEventListener('popstate',function(){if(tu_isDocs())tu_openDocs();else{$('docsov').style.display='none';document.body.style.overflow='';}});
if(tu_isDocs()){tu_openDocs();document.title='Docs - Thermal Vision';}
tu_checkAuth();
tu_loadGal();
</script></body></html>"""


def main():
    srv = ThreadingHTTPServer((BIND, PORT), H)
    srv.daemon_threads = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
