"""ui_tts/pill.py - Sound OS floating pill (our own design, nothing copied from other projects).

A small borderless bar that floats at the bottom of the screen:
  idle       dim "Say a command..."
  listening  blue sound bars that move with your voice
  heard      your sentence is typed on the bar (Arabic is shaped + right-to-left)
  ok / fail  a green check / a red cross, then back to idle

Needs Tkinter (+ Pillow for the smooth look; without Pillow a plain text bar is shown).
Drag it with the left mouse button, close it with a right click.
Never raises: if anything is missing it prints one clear line and stays silent.
"""
import ctypes
import ctypes.util
import math
import queue
import random
import threading
import time

try:
    from PIL import Image, ImageDraw, ImageTk
except Exception:                      # no Pillow: plain text bar
    Image = ImageDraw = ImageTk = None

# ---------- settings (change freely) ----------
W, H = 460, 84                 # pill size in pixels (scaled up on big screens)
BOTTOM_GAP = 64               # distance from the bottom edge of the screen
SS = 3                        # drawing supersampling (smoothness)
FPS = 30
RESULT_SECONDS = 2.2          # how long the check / cross stays
TYPE_CPS = 34                 # typewriter speed (characters / second)
IDLE_ALPHA, ACTIVE_ALPHA = 0.72, 0.98
HINT = "Say a command..."

BG_TOP, BG_BOT = (34, 37, 48), (19, 21, 27)
INK, GREY = (240, 243, 250), (140, 148, 166)
COLORS = {                    # accent per state
    "idle": (120, 140, 190),
    "listening": (80, 170, 255),
    "heard": (255, 190, 70),
    "ok": (52, 199, 89),
    "fail": (255, 69, 58),
}
LABELS = {"idle": "SOUND OS", "listening": "LISTENING", "heard": "YOU SAID", "ok": "DONE", "fail": "FAILED"}

_q = queue.Queue()
_lock = threading.Lock()
_thread = None
closed = False
_level = [0.0, 0.0]            # real mic level, time it was set


def _bridge():
    from . import coucou_bridge        # text helpers (fonts, Arabic shaping); imported late on purpose
    return coucou_bridge


def _say(msg):
    try:
        print("[ui_tts] " + msg, flush=True)
    except Exception:
        pass


def _ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


# ---------- rounded window shape (X11 / XWayland), so the corners are really transparent ----------
def _round_mask(w, h):
    big = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius=h * 2, fill=255)
    return big.resize((w, h), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0).convert("1")


def _apply_shape(win_id, mask):
    """Cut the window to `mask` with the X Shape extension. Returns True if it worked."""
    try:
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XCreateBitmapFromData.restype = ctypes.c_ulong
        x11.XCreateBitmapFromData.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_char_p,
                                              ctypes.c_uint, ctypes.c_uint]
        xext.XShapeCombineMask.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_ulong, ctypes.c_int]
        x11.XFreePixmap.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        dpy = x11.XOpenDisplay(None)
        if not dpy:
            return False
        w, h = mask.size
        data = mask.tobytes("raw", "1;R")            # XBM bit order: least significant bit first
        pm = x11.XCreateBitmapFromData(dpy, win_id, data, w, h)
        xext.XShapeCombineMask(dpy, win_id, 0, 0, 0, pm, 0)     # ShapeBounding, ShapeSet
        x11.XFreePixmap(dpy, pm)
        x11.XFlush(dpy)
        x11.XCloseDisplay(dpy)
        return True
    except Exception:
        return False


# ---------- drawing + animation (no Tk in here, so it can be tested without a screen) ----------
class Scene:
    def __init__(self, S=1.0, now=0.0):
        self.S, self.K = S, S * SS
        self.pw, self.ph = int(round(W * S)), int(round(H * S))
        self.t0 = self.state_t = self.type_t0 = now
        self.state = "idle"
        self.heard = self.partial = self.last = ""
        self.lvl = 0.0
        self.bg = None
        self.rnd = random.Random(7)
        self.noise = [0.0] * 5
        b = _bridge()
        self.shape = b._can_shape() and b._font(20) is not None and b._font(20, True) is not None

    # --- events ---
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

    # --- helpers ---
    def _bg(self):
        if self.bg is None:
            size = (self.pw * SS, self.ph * SS)
            top, bot = Image.new("RGB", size, BG_TOP), Image.new("RGB", size, BG_BOT)
            self.bg = Image.composite(bot, top, Image.linear_gradient("L").resize(size))
        return self.bg.copy()

    def _level(self, now, state):
        """0..1 loudness: the real mic level if fed, else a lively simulation while listening."""
        if now - _level[1] < 0.4:
            target = _level[0]
        elif state == "listening":
            target = 0.35 + 0.35 * abs(math.sin((now - self.t0) * 2.1)) + 0.2 * self.rnd.random()
        else:
            target = 0.0
        self.lvl += (target - self.lvl) * 0.25
        return self.lvl

    # --- one frame: returns (PIL RGB image, alpha for the window) ---
    def frame(self, now):
        if self.state in ("ok", "fail") and now - self.state_t > RESULT_SECONDS:
            self.state, self.state_t = "idle", now
        state, t = self.state, now - self.t0
        K = self.K
        acc = COLORS[state]
        lvl = self._level(now, state)
        im = self._bg()
        d = ImageDraw.Draw(im, "RGBA")
        w, h = self.pw * SS, self.ph * SS

        # body outline + soft top highlight
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, outline=acc + ((110 if state != "idle" else 50),),
                            width=max(2, int(K * 1.2)))
        d.rounded_rectangle((int(h * 0.45), int(K * 2), w - int(h * 0.45), int(K * 3)), radius=int(K),
                            fill=(255, 255, 255, 22))

        # badge (left): glow, disc, ring
        cx, cy, r = h / 2, h / 2, h * 0.31
        pulse = 1 + 0.06 * math.sin(t * 3) + lvl * 0.18
        for g in range(5):
            gr = r * pulse + (5 - g) * K * 3.2
            d.ellipse((cx - gr, cy - gr, cx + gr, cy + gr), fill=acc + (10 + g * 5,))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(22, 25, 33))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=acc + (230,), width=max(2, int(K * 1.4)))

        if state == "ok":                                   # check mark draws itself
            p = _ease((now - self.state_t) / 0.35)
            pts = [(cx - r * .42, cy + r * .02), (cx - r * .1, cy + r * .34), (cx + r * .46, cy - r * .3)]
            seg1 = pts[0], pts[1]
            d.line(seg1, fill=acc + (255,), width=int(K * 3.2), joint="curve")
            if p > 0.5:
                q = (p - 0.5) * 2
                end = (pts[1][0] + (pts[2][0] - pts[1][0]) * q, pts[1][1] + (pts[2][1] - pts[1][1]) * q)
                d.line((pts[1], end), fill=acc + (255,), width=int(K * 3.2))
        elif state == "fail":
            p = _ease((now - self.state_t) / 0.3)
            s = r * .36 * p
            d.line((cx - s, cy - s, cx + s, cy + s), fill=acc + (255,), width=int(K * 3.2))
            d.line((cx - s, cy + s, cx + s, cy - s), fill=acc + (255,), width=int(K * 3.2))
        else:                                               # five sound bars
            for i in range(5):
                if state == "listening":
                    tgt = 0.18 + lvl * 0.8 * abs(math.sin(t * 7.5 + i * 1.25))
                elif state == "heard":
                    tgt = 0.2 + 0.3 * (0.5 + 0.5 * math.sin(t * 5 - i * 0.9))     # calm travelling wave
                else:
                    tgt = 0.14 + 0.05 * math.sin(t * 1.6 + i)
                self.noise[i] += (tgt - self.noise[i]) * 0.35
                bh = r * 1.25 * max(0.1, self.noise[i])
                bx = cx + (i - 2) * K * 5.6
                d.rounded_rectangle((bx - K * 1.7, cy - bh, bx + K * 1.7, cy + bh), radius=int(K * 1.7),
                                    fill=acc + (255,))
            if state == "heard":                            # thinking ring around the badge
                a0 = (t * 260) % 360
                d.arc((cx - r - K * 4, cy - r - K * 4, cx + r + K * 4, cy + r + K * 4), a0, a0 + 90,
                      fill=acc + (230,), width=int(K * 2))

        self._text(d, state, now, t, acc)
        out = im.resize((self.pw, self.ph), Image.LANCZOS)
        alpha = IDLE_ALPHA if state == "idle" else ACTIVE_ALPHA
        return out, alpha

    # --- text: label + up to 2 lines, typewriter effect, Arabic shaping ---
    def _text(self, d, state, now, t, acc):
        b, K = _bridge(), self.K
        if state == "listening":
            full, dim = self.partial, not self.partial
            text = full or "." * (1 + int(now * 3) % 3)
        elif state in ("heard", "ok", "fail"):
            full, dim = self.heard, False
            text = full[:int(max(0.0, now - self.type_t0) * TYPE_CPS)]
        else:
            full, dim = self.last, True
            text = full or HINT
        x1, x2 = H + 6, W - 26                               # text zone (unscaled units)
        label = LABELS[state]
        if not self.shape:
            return
        rtl = b._is_rtl(text)
        small = b._font(10.5 * K)
        lines_big = None
        size = 18
        for size in (18, 16):
            font = b._font(size * K, arabic=False) if (not rtl or b._has_latin(text)) else b._font(size * K, arabic=True)
            lines_big = b._wrap(text, font, (x2 - x1) * K, rtl)
            if len(lines_big) <= 1:
                break
        lines_big = lines_big[-2:]
        col = GREY if dim else INK
        d.text((x1 * K, 14 * K), label, font=small, fill=acc if state != "idle" else GREY)
        ys = [36] if len(lines_big) == 1 else [31, 53]
        for ln, y in zip(lines_big, ys):
            if rtl:
                d.text((x2 * K, y * K), ln, font=font, fill=col, anchor="ra", direction="rtl")
            else:
                d.text((x1 * K, y * K), ln, font=font, fill=col, anchor="la")


# ---------- the Tk window ----------
def _run():
    global closed
    try:
        import tkinter as tk
    except Exception:
        closed = True
        _say("tkinter is missing, so no window can open.\n"
             "  Fix 1 (missing Tk):  Fedora: sudo dnf install python3-tkinter python3-pillow python3-pillow-tk\n"
             "                       Ubuntu: sudo apt install python3-tk python3-pil python3-pil.imagetk")
        return
    try:
        root = tk.Tk()
    except Exception as e:
        closed = True
        _say("cannot open a window (%s).\n"
             "  Run main.py from a Terminal on the desktop (not over ssh); `echo $DISPLAY` must not be empty." % e)
        return
    try:
        _build(root, tk)
        root.mainloop()
    except Exception as e:
        _say("the pill crashed: %r" % (e,))
    finally:
        closed = True


def _build(root, tk):
    global closed
    root.withdraw()
    root.overrideredirect(True)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.title("Sound OS")
    scale = 1.0
    try:
        scale = max(1.0, min(2.5, root.winfo_fpixels("1i") / 96.0))
    except Exception:
        pass
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    st = {"drag": None, "pos": None}

    if Image is None:
        _say("Pillow is missing, showing a plain bar (no animation).\n"
             "  Fix:  Fedora: sudo dnf install python3-pillow python3-pillow-tk   |   Ubuntu: sudo apt install python3-pil python3-pil.imagetk")
        pw, ph = W, 46
        lbl = tk.Label(root, text=HINT, bg="#15171c", fg="#f0f3fa", font=("DejaVu Sans", 13), bd=0)
        lbl.pack(fill="both", expand=True, ipadx=12, ipady=10)
        root.geometry("%dx%d+%d+%d" % (pw, ph, (sw - pw) // 2, sh - ph - BOTTOM_GAP))
        root.deiconify()
        scene = None
    else:
        scene = Scene(scale, time.time())
        pw, ph = scene.pw, scene.ph
        x = (sw - pw) // 2
        y_end = sh - ph - int(BOTTOM_GAP * scale)
        st["pos"] = [x, y_end]
        root.configure(bg="#13151b")
        photo = ImageTk.PhotoImage(Image.new("RGB", (pw, ph), BG_BOT))
        lbl = tk.Label(root, image=photo, bd=0, highlightthickness=0, bg="#13151b")
        lbl.pack()
        root.geometry("%dx%d+%d+%d" % (pw, ph, x, y_end + 40))
        root.update_idletasks()
        root.deiconify()
        root.update()
        shaped = _apply_shape(root.winfo_id(), _round_mask(pw, ph))
        scene.in_shape = shaped
    born = time.time()

    def close(_e=None):
        global closed
        closed = True
        try:
            root.destroy()
        except Exception:
            pass

    def press(e):
        st["drag"] = (e.x_root - root.winfo_x(), e.y_root - root.winfo_y())

    def move(e):
        if st["drag"]:
            nx, ny = e.x_root - st["drag"][0], e.y_root - st["drag"][1]
            st["pos"] = [nx, ny]
            root.geometry("+%d+%d" % (nx, ny))

    for wdg in (root, lbl):
        wdg.bind("<ButtonPress-1>", press)
        wdg.bind("<B1-Motion>", move)
        wdg.bind("<Button-3>", close)

    def tick():
        if closed:
            close()
            return
        now = time.time()
        try:
            while True:
                cmd, arg = _q.get_nowait()
                if scene is not None:
                    scene.handle(cmd, arg, now)
                elif cmd in ("heard", "partial"):
                    lbl.config(text=str(arg))
                elif cmd == "wake":
                    lbl.config(text="Listening...")
                elif cmd == "done":
                    lbl.config(text="Done" if arg else "Failed")
        except queue.Empty:
            pass
        if scene is not None:
            img, alpha = scene.frame(now)
            photo.paste(img)
            ease = _ease((now - born) / 0.5)                 # slide up + fade in when it appears
            if st["pos"] and not st["drag"]:
                root.geometry("+%d+%d" % (st["pos"][0], st["pos"][1] + int(40 * (1 - ease))))
            try:
                root.attributes("-alpha", alpha * ease)
            except Exception:
                pass
        root.after(int(1000 / FPS), tick)

    tick()


def _ensure_thread():
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, daemon=True)
            _thread.start()


# ---------- API used by coucou_bridge ----------
def start():
    if not closed:
        _ensure_thread()


def send(cmd, arg=None):
    try:
        if closed:
            return
        _ensure_thread()
        _q.put((cmd, arg))
    except Exception:
        pass


def set_level(level):
    try:
        _level[0], _level[1] = max(0.0, min(1.0, float(level))), time.time()
    except Exception:
        pass


def alive():
    return _thread is not None and _thread.is_alive() and not closed
