"""Sound OS - windowed voice UI (Tkinter + Pillow, anti-aliased). Never raises (CONTRACT Rule 7).

Pillow is needed for the smooth graphics:  pip install pillow
(Xubuntu/Ubuntu:  sudo apt install python3-pil python3-pil.imagetk)
Without Pillow a plain text window is shown instead.
"""

import math
import queue
import random
import threading
import time

try:
    from PIL import Image, ImageDraw
    _PIL = True
except Exception:
    _PIL = False

# ---------- Settings (tweak freely) ----------
LISTENING_TEXT = "Listening"  # shown while listening (3 dots animate after it)
W, H = 420, 700              # window size (logical pixels, scaled on hi-dpi screens)
SS = 3                       # anti-aliasing: draw 3x bigger, shrink down (2 = faster)
ALWAYS_ON_TOP = False
SPLASH_SECONDS = 1.4         # startup: Chris flies in (keep it short)
RESULT_SECONDS = 2.0         # how long the check / cross stays
TYPE_CPS = 34                # typewriter speed of the heard text (characters / second)
STATUS_Y = 546               # y of the status word
CARD = (24, 580, 396, 680)   # transcript card (x1, y1, x2, y2)
HINT = "Waiting for you..."  # card text while idle and nothing was heard yet

BG = (21, 23, 28)
BG_TOP = (30, 34, 46)         # background gradient (top) -> BG (bottom)
CARD_BG = (34, 38, 50)
ACCENT = (110, 168, 255)
GREEN = (52, 199, 89)
RED = (255, 59, 48)
WHITE = (255, 255, 255)
GREY = (139, 147, 161)
GOLD = (255, 214, 10)

BODY = (228, 234, 246)       # robot colors
BODY2 = (172, 185, 210)
FACE = (27, 32, 44)
EYE = (127, 227, 255)
BLUSH = (255, 140, 165)

HX, HY = 210, 150            # robot head center
CX, CY, R = 210, 400, 58     # voice circle center and radius
RINGS = 4

STATUS = {                   # state -> (text, show dots)
    "idle": ("Ready", False),
    "listening": (LISTENING_TEXT, True),
    "heard": ("Working", True),
    "ok": ("Done", False),
    "fail": ("Failed", False),
}

_CHECK = ((-20, 3), (-6, 17), (22, -15))

_q = queue.Queue()
_lock = threading.Lock()
_thread = None
_closed = False
_coucou = None
_coucou_checked = False


# ---------- small helpers ----------
def _hex(c):
    return "#%02x%02x%02x" % tuple(c)


def _mix(a, b, p):
    return tuple(int(a[i] + (b[i] - a[i]) * p) for i in range(3))


def _ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def _arc(cx, cy, rx, ry, a0, a1, n=28):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n),
             cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _star(cx, cy, r):
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.38
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


class _Pen:
    """Draws in logical units on a supersampled image, with an optional
    transform (scale + rotate around a pivot, then move)."""

    def __init__(self, d, k):
        self.d, self.k = d, k
        self.set()

    def set(self, ox=0.0, oy=0.0, rot=0.0, px=0.0, py=0.0, sx=1.0, sy=1.0):
        self.ox, self.oy, self.px, self.py = ox, oy, px, py
        self.sx, self.sy = sx, sy
        self.c, self.s = math.cos(rot), math.sin(rot)

    def pt(self, x, y):
        dx, dy = (x - self.px) * self.sx, (y - self.py) * self.sy
        return ((self.px + dx * self.c - dy * self.s + self.ox) * self.k,
                (self.py + dx * self.s + dy * self.c + self.oy) * self.k)

    def poly(self, pts, fill):
        self.d.polygon([self.pt(x, y) for x, y in pts], fill=fill)

    def ell(self, cx, cy, rx, ry, fill, rot=0.0):
        n = int(max(20, min(160, max(rx, ry) * self.k * 0.6)))
        c, s = math.cos(rot), math.sin(rot)
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = rx * math.cos(a), ry * math.sin(a)
            pts.append((cx + x * c - y * s, cy + x * s + y * c))
        self.poly(pts, fill)

    def rrect(self, x1, y1, x2, y2, r, fill):
        pts = []
        for cx, cy, a0 in ((x2 - r, y1 + r, -90), (x2 - r, y2 - r, 0),
                           (x1 + r, y2 - r, 90), (x1 + r, y1 + r, 180)):
            for i in range(10):
                a = math.radians(a0 + 90 * i / 9)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, fill)

    def stroke(self, pts, w, fill):
        """Thick line with round caps (use opaque colors)."""
        P = [self.pt(x, y) for x, y in pts]
        wk = max(1, int(round(w * self.k * abs(self.sx))))
        self.d.line(P, fill=fill, width=wk, joint="curve")
        r = wk / 2.0
        for x, y in (P[0], P[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def oval(self, cx, cy, rx, ry, fill=None, outline=None, width=1.0):
        """Exact ellipse, no transform (call after set() with defaults)."""
        k = self.k
        self.d.ellipse(((cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k),
                       fill=fill, outline=outline, width=max(1, int(width * k)))


# ---------- text drawing (Arabic needs shaping + right-to-left: Pillow raqm) ----------
_FONTS_AR = (       # Arabic-capable fonts (nicest first)
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)
_FONTS_LAT = (      # fonts with Latin letters (also used for mixed Arabic + English)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)
_font_cache = {}


def _can_shape():
    try:
        from PIL import features
        return bool(features.check("raqm"))
    except Exception:
        return False


def _font(px, arabic=False):
    """Font at px pixels (cached). arabic=True -> pick an Arabic-capable font. None if not found."""
    try:
        key = (int(px), bool(arabic))
        if key not in _font_cache:
            import os
            from PIL import ImageFont
            path = next((f for f in (_FONTS_AR if arabic else _FONTS_LAT) if os.path.exists(f)), None)
            if path is None:
                _font_cache[key] = None
            else:
                kw = {"layout_engine": ImageFont.Layout.RAQM} if _can_shape() else {}
                _font_cache[key] = ImageFont.truetype(path, key[0], **kw)
        return _font_cache[key]
    except Exception:
        return None


def _has_latin(text):
    return any(c.isascii() and c.isalpha() for c in text)


def _is_rtl(text):
    return any("\u0590" <= c <= "\u08ff" for c in text)


def _wrap(text, font, max_w, rtl):
    """Greedy word wrap (logical order). Returns a list of lines."""
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if cur and font.getlength(t, direction="rtl" if rtl else "ltr") > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


# ---------- Coucou island (optional) ----------
def _try_coucou(name, *args):
    """Call coucou.<name>(*args) if a 'coucou' module with it exists. True if handled."""
    global _coucou, _coucou_checked
    try:
        if not _coucou_checked:
            _coucou_checked = True
            try:
                import coucou  # ASSUMPTION: module name and function names
                _coucou = coucou
            except Exception:
                _coucou = None
        fn = getattr(_coucou, name, None) if _coucou else None
        if callable(fn):
            fn(*args)
            return True
    except Exception:
        pass
    return False


# ---------- the drawing + animation logic (no Tk in here) ----------
class _Scene:
    def __init__(self, S, now):
        self.S, self.K = S, S * SS
        self.pw, self.ph = int(round(W * S)), int(round(H * S))
        self.t0 = self.state_t = now
        self.state = "splash"
        self.level = self.real_level = self.real_t = 0.0
        self.heard = ""
        self.partial = ""                                # live text while listening
        self.last = ""                                   # last command (shown dim when idle)
        self.type_t0 = now
        self.shape = _can_shape() and _font(20) is not None and _font(20, True) is not None   # draw text with Pillow?
        self.bg = None                                   # cached gradient background
        self.bub = 0.0                                   # thought bubble size 0..1
        # smoothed pose: head x, head y, head tilt, left hand xy, right hand xy
        self.pose = [0.0, 0.0, 0.0, 158.0, 226.0, 262.0, 226.0]

    def handle(self, cmd, arg, now):
        if cmd == "wake":
            self.state, self.state_t, self.heard, self.partial = "listening", now, "", ""
        elif cmd == "partial":
            if self.state != "listening":
                self.state, self.state_t = "listening", now
            self.partial = str(arg)
        elif cmd == "heard":
            self.state, self.state_t, self.heard = "heard", now, str(arg)
            self.partial, self.last, self.type_t0 = "", str(arg), now
        elif cmd == "done":
            self.state, self.state_t = ("ok" if arg else "fail"), now
        elif cmd == "level":
            self.real_level = max(0.0, min(1.0, float(arg)))
            self.real_t = now

    def _new(self, bg):
        im = Image.new("RGB", (self.pw * SS, self.ph * SS), bg)
        return im, _Pen(ImageDraw.Draw(im, "RGBA"), self.K)

    def _new_main(self):
        """Main-screen canvas: soft vertical gradient (built once, then copied)."""
        if self.bg is None:
            size = (self.pw * SS, self.ph * SS)
            top, bot = Image.new("RGB", size, BG_TOP), Image.new("RGB", size, BG)
            self.bg = Image.composite(bot, top, Image.linear_gradient("L").resize(size))
        im = self.bg.copy()
        return im, _Pen(ImageDraw.Draw(im, "RGBA"), self.K)

    def frame(self, now, measure):
        """Returns (PIL image, info). info is None during the splash."""
        t = now - self.t0
        if self.state == "splash":
            if t < SPLASH_SECONDS:
                return self._splash(t), None
            self.state, self.state_t = "idle", now
        return self._main(now, t, measure)

    # ----- splash: Chris flies in, lands, and switches the app on -----
    def _splash(self, t):
        FLY = 0.65
        im, pen = self._new(WHITE)

        p = (t - 0.55) / 0.7                     # dark app background spreads out from Chris
        if p > 0:
            rr = 1100 * _ease_out(p)
            pen.oval(HX, HY + 20, rr, rr, fill=BG)

        if t < FLY:                               # flight (from the top right)
            q = t / FLY
            e = _ease_out(q)
            off = (260 * (1 - e),
                   -230 * (1 - e) - 30 * math.sin(math.pi * e) + 5 * math.sin(q * 16) * (1 - e))
            w = math.sin(t * 22) * 6
            pose = [0, 0, -0.3 * (1 - e), 140, 190 + w, 280, 190 - w]
            pen.set()
            bx, by = 0.75, -0.66                  # speed lines trail behind him
            for po, ln in ((-26, 70), (0, 95), (26, 70)):
                x0 = 210 + off[0] + 0.66 * po + bx * 40
                y0 = 205 + off[1] + 0.75 * po + by * 40
                pen.stroke([(x0, y0), (x0 + bx * ln * (1 - e), y0 + by * ln * (1 - e))],
                           4, (200, 212, 238))
            self._robot(pen, "idle", False, t, 0.0, 0.0, ACCENT, off=off, shadow=0.0,
                        pose_to=pose, sparkles=False)
        else:                                     # landing hop, arms up
            st = t - FLY
            hop = abs(math.sin(st * 7)) * math.exp(-st * 1.6)
            pose = [0, -18 * hop, 0.05 * math.sin(st * 9) * math.exp(-st * 1.2),
                    124, 166 + math.sin(st * 14) * 4, 296, 166 - math.sin(st * 14) * 4]
            self._robot(pen, "idle", False, t, st, 0.0, ACCENT, shadow=min(1.0, st / 0.2),
                        pose_to=pose, happy=True, sparkles=False)

        pp = (t - 0.75) / 0.45                    # the voice circle pops in
        if pp > 0:
            c1 = 1.70158
            q = min(1.0, pp) - 1
            self._orb(pen, "idle", t, 0.0, 0.0, ACCENT, 0.06, pop=1 + (c1 + 1) * q ** 3 + c1 * q ** 2)
        return im.reduce(SS)

    # ----- main screen -----
    def _main(self, now, t, measure):
        st = now - self.state_t
        state = self.state
        if state in ("ok", "fail") and st > RESULT_SECONDS:
            self.state, self.state_t, self.heard = "idle", now, ""
            state, st = "idle", 0.0
        thinking = state in ("listening", "heard")

        # voice level: real (set_level) if recent, else simulated while listening
        if state == "listening":
            if now - self.real_t < 0.6:
                target = self.real_level
            else:
                target = min(1.0, 0.2 + 0.6 * abs(math.sin(t * 3.1) * math.sin(t * 1.1 + 0.6))
                             + 0.2 * random.random())
        elif state == "heard":
            target = 0.15
        elif state == "idle":
            target = 0.06
        else:
            target = 0.6 * max(0.0, 1 - st / 0.8)
        self.level += (target - self.level) * 0.3
        accent = GREEN if state == "ok" else RED if state == "fail" else ACCENT

        dx = 0.0                                             # shake on failure
        if state == "fail" and st > 0.3:
            k = st - 0.3
            if k < 0.6:
                dx = 9 * math.sin(k * 45) * (1 - k / 0.6)

        self.bub += ((1.0 if thinking else 0.0) - self.bub) * 0.22

        im, pen = self._new_main()
        self._particles(pen, t, accent)
        self._robot(pen, state, thinking, t, st, dx, accent)
        self._orb(pen, state, t, st, dx, accent, self.level)
        shown = self._card(pen, state, now, t, accent)

        text, dotted = STATUS[state]
        tw = measure(text) / self.S
        x0 = (W - (tw + (38 if dotted else 0))) / 2
        if dotted:
            pen.set()
            for i in range(3):
                pen.oval(x0 + tw + 11 + i * 12, STATUS_Y + 7 - 7 * max(0.0, math.sin(t * 6 - i * 0.9)),
                         3.4, 3.4, fill=WHITE)
        info = {
            "text": text, "x": x0,
            "color": _hex(GREEN if state == "ok" else RED if state == "fail" else WHITE),
            "sub": "" if self.shape else shown,      # no raqm: Tk draws the text instead
        }
        return im.reduce(SS), info

    # ----- background particles (slow rising dots, brighter while listening) -----
    def _particles(self, pen, t, accent):
        pen.set()
        for i in range(16):
            x = (37 * i * 7919 % W) + 14 * math.sin(t * 0.35 + i)
            y = (H + 20) - ((t * (7 + i % 5 * 3) + i * 53) % (H + 40))
            r = 1.2 + (i % 3) * 0.8
            a = 28 + 22 * math.sin(t * 0.9 + i) + (30 if self.state == "listening" else 0)
            pen.oval(x, y, r, r, fill=accent + (int(max(10, a)),))

    # ----- transcript card: live text, typewriter effect, Arabic shaping -----
    def _card(self, pen, state, now, t, accent):
        """Draws the card. Returns the text being shown (for the Tk fallback)."""
        x1, y1, x2, y2 = CARD
        pen.set()
        edge = accent + (70,) if state in ("listening", "heard") else (255, 255, 255, 28)
        pen.rrect(x1 - 1, y1 - 1, x2 + 1, y2 + 1, 19, edge)
        pen.rrect(x1, y1, x2, y2, 18, CARD_BG)

        if state == "listening":
            full, dim, label = self.partial, not self.partial, "LISTENING"
            text = full or "..."
        elif state in ("heard", "ok", "fail"):
            full, dim, label = self.heard, False, "YOU SAID"
            n = int(max(0.0, now - self.type_t0) * TYPE_CPS)
            text = full[:n]
        else:
            full, dim, label = self.last, True, "LAST COMMAND" if self.last else "READY"
            text = full or HINT

        if self.shape:
            small = _font(11 * self.K)
            rtl = _is_rtl(text)
            big = _font(19 * self.K, arabic=rtl and not _has_latin(text)) if not (rtl and _has_latin(text)) \
                else _font(19 * self.K)            # mixed Arabic + English: DejaVu covers both
            col = GREY if dim else WHITE
            pen.d.text(((x1 + 16) * self.K, (y1 + 10) * self.K), label, font=small, fill=GREY)
            lines = _wrap(text, big, (x2 - x1 - 32) * self.K, rtl)[-2:]           # last 2 lines
            for i, ln in enumerate(lines):
                yy = (y1 + 34 + i * 27) * self.K
                if rtl:
                    pen.d.text(((x2 - 16) * self.K, yy), ln, font=big, fill=col, anchor="ra", direction="rtl")
                else:
                    pen.d.text(((x1 + 16) * self.K, yy), ln, font=big, fill=col, anchor="la")
        return text

    # ----- the robot -----
    def _robot(self, pen, state, thinking, t, st, dx, accent,
               off=(0.0, 0.0), shadow=1.0, pose_to=None, happy=False, sparkles=True):
        ok, fail = state == "ok", state == "fail"
        face_ok = ok or happy

        # target pose for this state, then ease toward it
        sw = math.sin(t * 1.6)
        if thinking:
            tg = [3 * math.sin(t * 1.1), 2 * math.sin(t * 3.0), 0.14 + 0.06 * math.sin(t * 1.5),
                  166, 230 + 2 * sw, 278, 186]
        elif ok:
            hop = abs(math.sin(st * 7)) * math.exp(-st * 1.6)
            w = math.sin(st * 14) * 5
            tg = [0, -22 * hop, 0.07 * math.sin(st * 9) * math.exp(-st * 1.2),
                  124, 166 + w, 296, 166 - w]
        elif fail:
            e = _ease_out(st / 0.5)
            tg = [0, 8 * e + 1.5 * math.sin(t * 2), -0.14 * e, 166, 238, 254, 238]
        else:
            tg = [5 * math.sin(t * 0.9), 3 * math.sin(t * 1.7), 0.10 * math.sin(t * 1.3),
                  158 + 2 * sw, 226, 262 - 2 * sw, 226]
        if pose_to is not None:
            tg = pose_to
        f = 0.5 if pose_to is not None else 0.3
        for i in range(7):
            self.pose[i] += (tg[i] - self.pose[i]) * f
        hx_, hy_, rot, lhx, lhy, rhx, rhy = self.pose

        # ground shadow (shrinks when the robot hops)
        pen.set()
        lift = min(1.0, max(0.0, -hy_) / 22)
        if shadow > 0.02:
            pen.oval(210 + dx + off[0], 246, 54 * (1 - 0.25 * lift), 8 * (1 - 0.25 * lift),
                     fill=(0, 0, 0, int(110 * shadow)))

        # arms + body
        pen.set(ox=dx + hx_ * 0.3 + off[0], oy=hy_ * 0.5 + off[1])
        pen.stroke([(178, 204), (lhx, lhy)], 15, BODY2)
        pen.stroke([(242, 204), (rhx, rhy)], 15, BODY2)
        pen.ell(210, 210, 40, 33, BODY2)
        pen.ell(210, 207, 40, 32, BODY)
        pen.ell(210, 212, 15, 11, FACE)
        glow = 0.55 + 0.45 * math.sin(t * 3)
        pen.ell(210, 212, 6.5, 6.5, accent + (int(130 + 125 * glow),))

        # head (tilts around the neck)
        pen.set(ox=HX + dx + hx_ + off[0], oy=HY + hy_ + off[1], rot=rot, px=0, py=50)
        pen.ell(-66, 4, 9, 17, BODY2)                      # ears
        pen.ell(66, 4, 9, 17, BODY2)

        ax = 6 * math.sin(t * 2.2)                          # antenna
        ay = -74
        if thinking:
            ax = 8 * math.sin(t * 5)
        elif ok:
            ax = 0
        elif fail:
            ax, ay = -13, -62
        pen.stroke([(0, -42), (ax * 0.5, -58), (ax, ay + 4)], 4, BODY2)
        pulse = 0.6 + 0.4 * math.sin(t * (7 if thinking else 3))
        pen.ell(ax, ay, 15, 15, accent + (int(70 * pulse),))
        pen.ell(ax, ay, 8, 8, _mix(accent, WHITE, 0.25 * pulse) if thinking else accent)

        pen.rrect(-62, -46, 62, 48, 42, BODY2)              # head
        pen.rrect(-62, -48, 62, 44, 42, BODY)
        pen.ell(-36, -33, 16, 6, (255, 255, 255, 120), rot=-0.4)
        pen.rrect(-48, -30, 48, 28, 24, FACE)               # face plate
        pen.ell(-37, 13, 7.5, 4.5, BLUSH + ((200 if face_ok else 95),))
        pen.ell(37, 13, 7.5, 4.5, BLUSH + ((200 if face_ok else 95),))

        # eyes
        if thinking:
            lx, ly = 6 * math.sin(t * 1.7), -4 + 1.5 * math.sin(t * 2.3)
        elif fail:
            lx, ly = 0.0, 4.0
        else:
            lx, ly = 3 * math.sin(t * 0.8), 1.5 * math.sin(t * 0.55)
        u = t % 3.8
        blink = 1 - 0.92 * math.sin(math.pi * u / 0.14) if (u < 0.14 and not thinking) else 1.0
        for sg in (-1, 1):
            cx, cy = sg * 20 + lx, -3 + ly
            if face_ok:                                       # happy ^ ^
                pen.stroke(_arc(cx, cy + 4, 9, 9, math.pi * 1.05, math.pi * 1.95), 4.5, EYE)
            else:
                rx, ry = (7.5, 8.5) if fail else (8.5, 11)
                pen.ell(cx, cy, rx + 5, ry * blink + 5, EYE + (45,))
                pen.ell(cx, cy, rx, ry * blink, EYE)
                if blink > 0.5:
                    pen.ell(cx + 2.5, cy - 3.5, 2.6, 2.6, WHITE)
        if fail:                                              # sad brows + tear
            pen.stroke([(-31, -14), (-12, -22)], 3.2, EYE)
            pen.stroke([(12, -22), (31, -14)], 3.2, EYE)
            if st > 0.5:
                pr = ((st - 0.5) * 0.8) % 1
                pen.ell(-24, 9 + pr * 16, 3, 4.6, (130, 200, 255, int(220 * (1 - pr))))

        # mouth
        if face_ok:
            pen.poly(_arc(0, 8, 11, 12, 0, math.pi), (255, 132, 150))
        elif fail:
            pen.stroke(_arc(0, 24, 9, 7, math.pi * 1.15, math.pi * 1.85), 3.2, EYE)
        elif thinking:
            pen.ell(lx * 0.5, 15, 3.6, 4.2 + 0.8 * math.sin(t * 5), EYE)
        else:
            pen.stroke(_arc(0, 9, 9, 6.5, math.pi * 0.2, math.pi * 0.8), 3.2, EYE)

        # thought bubble while listening / working
        if self.bub > 0.03:
            sc = _ease_out(self.bub)
            pen.set(ox=dx + hx_ * 0.5, oy=hy_ * 0.5, px=338, py=70, sx=sc, sy=sc)
            CL = (240, 244, 252)
            pen.ell(268, 118, 3.4, 3.4, CL)
            pen.ell(283, 100, 5.5, 5.5, CL)
            pen.ell(338, 70, 40, 22, CL)
            pen.ell(316, 64, 16, 15, CL)
            pen.ell(342, 55, 20, 18, CL)
            pen.ell(362, 65, 16, 14, CL)
            for i in range(3):
                yy = 70 - 5 * max(0.0, math.sin(t * 6 - i * 0.9))
                pen.ell(318 + i * 20, yy, 4.5, 4.5, (70, 85, 120))

        # sparkles when done
        if sparkles and ok and st < 1.7:
            pen.set()
            life = st / 1.7
            for i in range(7):
                a = i * 2 * math.pi / 7 + 0.4 + st * 0.5
                rad = 80 + 55 * _ease_out(life)
                col = (GREEN if i % 2 else GOLD) + (int(255 * (1 - life * life)),)
                pen.poly(_star(HX + math.cos(a) * rad * 1.25, HY + 10 + math.sin(a) * rad * 0.8,
                               4 + 7 * (1 - life)), col)

    # ----- voice circle with waves, check and cross -----
    def _orb(self, pen, state, t, st, dx, accent, lvl, pop=1.0):
        pen.set()
        if pop < 0.02:
            return
        fx = CX + dx
        if state == "ok":
            scale = 1 + 0.08 * math.sin(math.pi * min(1.0, st / 0.35))
        else:
            scale = 1 + 0.015 * math.sin(t * 2)
        r = R * scale * (1 + 0.05 * lvl) * pop
        boost = min(1.0, 0.25 + lvl * 1.5)
        for g in range(4):                                    # soft glow behind the circle
            gr = r + 70 - g * 14
            pen.oval(fx, CY, gr, gr, fill=accent + (int(10 * boost + 4 * g),))

        for i in reversed(range(RINGS)):                      # semi-transparent wavy rings
            base = r + 15 * pop * (i + 1)
            a = (0.20 - 0.035 * i) * boost
            pts = []
            for j in range(120):
                th = j / 120 * 2 * math.pi
                rad = (base + lvl * 11 * math.sin(3 * th + t * 3.6 - i * 1.1)
                       + lvl * 6 * math.sin(5 * th - t * 2.4 + i))
                pts.append((fx + rad * math.cos(th), CY + rad * math.sin(th)))
            pen.poly(pts, accent + (int(255 * a),))
            edge = [pen.pt(x, y) for x, y in pts]
            pen.d.line(edge + [edge[0]], fill=accent + (int(150 * boost * (1 - i * 0.2)),),
                       width=max(1, int(1.4 * self.K)), joint="curve")
        pen.oval(fx, CY, r, r, fill=WHITE)

        if state == "ok":                                     # check draws itself
            la, lb = math.hypot(14, 14), math.hypot(28, 32)
            d = min(1.0, st / 0.45) * (la + lb)
            A, B, C = _CHECK
            if d <= la:
                p = d / la
                pts = [A, (A[0] + (B[0] - A[0]) * p, A[1] + (B[1] - A[1]) * p)]
            else:
                p = (d - la) / lb
                pts = [A, B, (B[0] + (C[0] - B[0]) * p, B[1] + (C[1] - B[1]) * p)]
            pen.stroke([(fx + x, CY + y) for x, y in pts], 9, GREEN)
        elif state == "fail":                                 # cross, then the shake
            for n, (a, b) in enumerate((((-16, -16), (16, 16)), ((16, -16), (-16, 16)))):
                p = max(0.0, min(1.0, min(1.0, st / 0.3) * 2 - n))
                if p > 0:
                    pen.stroke([(fx + a[0], CY + a[1]),
                                (fx + a[0] + (b[0] - a[0]) * p, CY + a[1] + (b[1] - a[1]) * p)],
                               9, RED)


# ---------- Tkinter windows (run in their own thread) ----------
class _App:
    def __init__(self, root, tk, tkfont, ImageTk, S):
        self.root, self.S = root, S
        self.scene = sc = _Scene(S, time.time())
        root.title("Sound OS")
        root.resizable(False, False)
        root.configure(bg=_hex(WHITE))
        try:
            root.attributes("-topmost", ALWAYS_ON_TOP)
        except Exception:
            pass
        x = (root.winfo_screenwidth() - sc.pw) // 2
        y = max(0, (root.winfo_screenheight() - sc.ph) // 2 - 20)
        root.geometry(f"{sc.pw}x{sc.ph}+{x}+{y}")
        root.protocol("WM_DELETE_WINDOW", self.close)

        cv = self.cv = tk.Canvas(root, width=sc.pw, height=sc.ph,
                                 bg=_hex(WHITE), highlightthickness=0)
        cv.pack()
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (sc.pw, sc.ph), WHITE))
        cv.create_image(0, 0, image=self.photo, anchor="nw")

        def px(v):
            return -max(1, int(round(v * S)))
        self.f_status = tkfont.Font(family="Helvetica", size=px(24), weight="bold")
        f_sub = tkfont.Font(family="Helvetica", size=px(14))
        f_title = tkfont.Font(family="Helvetica", size=px(12), weight="bold")
        h = "hidden"
        self.t_title = cv.create_text(W / 2 * S, 28 * S, text="SOUND OS", fill=_hex(GREY),
                                      font=f_title, state=h)
        self.t_status = cv.create_text(0, STATUS_Y * S, anchor="w", text="", fill=_hex(WHITE),
                                       font=self.f_status, state=h)
        self.t_sub = cv.create_text(W / 2 * S, (CARD[1] + 52) * S, text="", fill=_hex(WHITE), font=f_sub,
                                    width=int((CARD[2] - CARD[0] - 32) * S), justify="center", state=h)
        self.items = (self.t_title, self.t_status, self.t_sub)
        self.ui = False
        self.tick()

    def close(self):
        global _closed
        _closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def drain(self, now):
        while True:
            try:
                cmd, arg = _q.get_nowait()
            except queue.Empty:
                return
            try:
                self.scene.handle(cmd, arg, now)
            except Exception:
                pass

    def tick(self):
        t0 = time.time()
        try:
            sc = self.scene
            if sc.state != "splash":
                self.drain(t0)
            img, info = sc.frame(t0, self.f_status.measure)
            self.photo.paste(img)
            self.show_text(info)
        except Exception:
            pass
        try:
            self.root.after(max(1, int(33 - (time.time() - t0) * 1000)), self.tick)
        except Exception:
            pass

    def show_text(self, info):
        cv, S = self.cv, self.S
        if info is None:
            return
        if not self.ui:
            self.ui = True
            for it in self.items:
                cv.itemconfigure(it, state="normal")
        cv.coords(self.t_status, info["x"] * S, STATUS_Y * S)
        cv.itemconfigure(self.t_status, text=info["text"], fill=info["color"])
        cv.itemconfigure(self.t_sub, text=info["sub"])


class _Plain:
    """Fallback when Pillow is missing: simple text window, no animation."""

    def __init__(self, root, tk):
        self.root = root
        root.title("Sound OS")
        root.geometry("360x200")
        root.configure(bg=_hex(BG))
        self.lbl = tk.Label(root, text="Ready", fg="white", bg=_hex(BG),
                            font=("Helvetica", 20, "bold"), wraplength=320)
        self.lbl.pack(expand=True)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll()

    def close(self):
        global _closed
        _closed = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def poll(self):
        try:
            while True:
                cmd, arg = _q.get_nowait()
                if cmd == "wake":
                    self.lbl.config(text=LISTENING_TEXT + "...")
                elif cmd == "partial":
                    self.lbl.config(text=LISTENING_TEXT + ": " + str(arg))
                elif cmd == "heard":
                    self.lbl.config(text="Heard: " + str(arg))
                elif cmd == "done":
                    self.lbl.config(text="Done" if arg else "Failed")
        except queue.Empty:
            pass
        except Exception:
            pass
        try:
            self.root.after(50, self.poll)
        except Exception:
            pass


def _warn(msg):
    try:
        print("[ui_tts] " + msg)
    except Exception:
        pass


def _run():
    global _closed
    try:
        try:
            import ctypes                      # Windows: crisp (non-blurry) window
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        import tkinter as tk
        from tkinter import font as tkfont
        root = tk.Tk()
    except Exception as e:
        _closed = True      # no display / no tkinter: say why once, then stop retrying
        _warn("cannot open the window (%s: %s).\n"
              "  Fix 1 (missing Tk):  sudo apt install python3-tk python3-pil python3-pil.imagetk\n"
              "  Fix 2 (no screen):   run from the desktop Terminal, not ssh;  echo $DISPLAY  must not be empty"
              % (type(e).__name__, e))
        return
    try:
        ImageTk = None
        if _PIL:
            try:
                from PIL import ImageTk
            except Exception:
                ImageTk = None
        if ImageTk is not None:
            S = max(1.0, min(3.0, root.winfo_fpixels("1i") / 96.0))
            _App(root, tk, tkfont, ImageTk, S)
        else:
            _warn("Pillow is missing, showing the plain window (no animation).\n"
                  "  Fix:  sudo apt install python3-pil python3-pil.imagetk   (or: pip install pillow)")
            _Plain(root, tk)
        root.mainloop()
    except Exception as e:
        _warn("the window crashed: %r" % (e,))


def _ensure_thread():
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, daemon=True)
            _thread.start()


def _send(cmd, arg=None):
    try:
        if _closed:         # user closed the window: stay closed
            return
        _ensure_thread()
        _q.put((cmd, arg))
    except Exception:
        pass


# ---------- Public API ----------
def start() -> None:
    """Open the window now (logo spin plays). Optional: on_wake() also opens it."""
    try:
        if not _closed:
            _ensure_thread()
    except Exception:
        pass


def set_level(level) -> None:
    """Optional: feed the real mic loudness (0.0 - 1.0) to drive the waves."""
    try:
        _send("level", float(level))
    except Exception:
        pass


def on_wake() -> None:
    try:
        if not _try_coucou("on_wake"):
            _send("wake")
    except Exception:
        pass


def on_partial(text) -> None:
    """Optional: live (not final) text while the user is still speaking."""
    try:
        text = str(text)
        text = text if len(text) <= 80 else "..." + text[-77:]
        if not _try_coucou("on_partial", text):
            _send("partial", text)
    except Exception:
        pass


def linger(seconds=RESULT_SECONDS + 0.8) -> None:
    """Keep the process alive a moment so the last result is visible (one-shot runs)."""
    try:
        if _thread is not None and _thread.is_alive() and not _closed:
            time.sleep(seconds)
    except Exception:
        pass


def on_heard(text) -> None:
    try:
        text = str(text)
        text = text if len(text) <= 80 else text[:77] + "..."
        if not _try_coucou("on_heard", text):
            _send("heard", text)
    except Exception:
        pass


def on_done(success) -> None:
    try:
        ok = bool(success)
        if not _try_coucou("on_done", ok):
            _send("done", ok)
    except Exception:
        pass
