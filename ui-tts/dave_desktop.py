"""Dave on your desktop: no window frame, no box, just Dave floating above everything.

How it fits together:
    dave_character.py  Dave himself: looks, moods, movement (no windows, no libraries)
    dave_stage.py      paints him with Qt on a see-through background
    dave_desktop.py    this file: the public functions + the floating window (PySide6)
    dave_voice.py      his voice (Piper); drives his mouth through set_mouth()

The window runs as a small separate program that this module starts for you the first
time you call a function below, so it never fights your own program for the screen.
When your program ends, Dave closes by himself.

Needs:   python -m pip install PySide6
Debug:   set the environment variable DAVE_DEBUG=1 to see every message Dave receives.
Linux:   the desktop needs its "compositor" on for see-through windows (Xfce: Settings >
         Window Manager Tweaks > Compositor).

Public functions never raise (CONTRACT Rule 7).
"""

import json
import math
import os
import queue
import subprocess
import sys
import threading
import time

SPEAK_OWN_LINES = True        # Dave says his own greeting and click lines out loud
CLICK_LINES = ("Hi!", "Need something?", "I'm listening!", "Beep. Boop!")

_proc = None
_gone = False                 # Dave has been closed: don't bring him back uninvited
_lock = threading.Lock()


# =====================================================================
#  Public functions (used by your program)
# =====================================================================
def _spawn():
    global _proc, _gone
    with _lock:
        if _gone:
            return None
        if _proc is not None:
            if _proc.poll() is None:
                return _proc
            _gone = True                  # he quit (or could not start): leave him quit
            return None
        pkg = __name__.rpartition(".")[0] or "ui_tts"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flags = 0x08000000 if sys.platform == "win32" else 0     # no extra console window
        _proc = subprocess.Popen([sys.executable, "-m", pkg + ".dave_desktop"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                 encoding="utf-8", cwd=root, creationflags=flags)
        threading.Thread(target=_read_window, args=(_proc,), daemon=True).start()
        if SPEAK_OWN_LINES:
            threading.Thread(target=_warm_voice, daemon=True).start()
        return _proc


def _read_window(proc):
    """The window program tells us things on its output: lines starting with '@dave ' are
    requests (e.g. 'say this out loud'); anything else is a message for the person
    running the program and is passed on."""
    try:
        for line in proc.stdout:
            if line.startswith("@dave "):
                try:
                    _on_window_event(json.loads(line[6:]))
                except Exception:
                    pass
            else:
                print(line, end="", flush=True)
    except Exception:
        pass


def _on_window_event(event):
    text = event.get("speak")
    if text and SPEAK_OWN_LINES:
        from . import dave_voice
        dave_voice.speak(text, "en")


def _warm_voice():
    """Get his own lines ready while the window starts, so they play instantly."""
    try:
        from . import dave_voice
        from .dave_character import GREETING
        for line in (GREETING,) + CLICK_LINES:
            dave_voice.warm(line, "en")
    except Exception:
        pass


def _send(cmd, arg=None):
    try:
        p = _spawn()
        if p is None:
            return
        p.stdin.write(json.dumps({"cmd": cmd, "arg": arg}) + "\n")
        p.stdin.flush()
    except Exception:
        pass


def start() -> None:
    """Put Dave on the desktop now. Optional: any other function below also starts him."""
    try:
        _spawn()
    except Exception:
        pass


def stop() -> None:
    """Send Dave home. He will not come back until your program starts again."""
    global _gone
    try:
        _send("quit")
        with _lock:
            _gone = True
            p = _proc
        if p is not None:
            try:
                p.stdin.close()
                p.wait(timeout=3)
            except Exception:
                p.kill()
    except Exception:
        pass


def on_wake() -> None:
    try:
        _send("wake")
    except Exception:
        pass


def on_heard(text) -> None:
    try:
        text = str(text)
        _send("heard", text if len(text) <= 80 else text[:77] + "...")
    except Exception:
        pass


def on_done(success) -> None:
    try:
        _send("done", bool(success))
    except Exception:
        pass


def set_level(level) -> None:
    """Optional: real mic loudness (0.0 - 1.0)."""
    try:
        _send("level", float(level))
    except Exception:
        pass


def set_mouth(level) -> None:
    """How open Dave's mouth is, 0.0 - 1.0. The voice engine (dave_voice.py) calls this for you
    while he speaks; if no update comes for 0.4 s his mouth closes by itself."""
    try:
        _send("mouth", float(level))
    except Exception:
        pass


def hush() -> None:
    """Close Dave's speech bubble right away."""
    try:
        _send("hush")
    except Exception:
        pass


def say(text, seconds=3.0) -> None:
    """Dave shows a speech bubble with this text for a few seconds."""
    try:
        _send("say", {"text": str(text), "seconds": float(seconds)})
    except Exception:
        pass


# =====================================================================
#  The floating window (runs inside Dave's own small program)
# =====================================================================
def _make_window_class():
    from PySide6 import QtCore, QtGui, QtWidgets
    from . import dave_stage
    from .dave_character import GREETING, GREET_SECONDS
    from .dave_character import ease_back as _ease_back, ease_out as _ease_out

    Qt = QtCore.Qt
    DEBUG = bool(os.environ.get("DAVE_DEBUG"))
    FLAGS = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool)
    TEXT_FLAGS = Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value
    FLY_IN, WAVE, FLY_OUT = 1.1, 1.5, 1.3     # seconds: fly in, wave hello, fly away
    MIN_STATE_SECONDS = 0.7                    # each mood stays at least this long, so none is missed
    CENTER = QtCore.QPointF(190, 175)          # Dave's middle inside the window (he shrinks toward it)
    SW, SH = dave_stage.SW, dave_stage.SH

    class DaveWindow(QtWidgets.QWidget):
        def __init__(self, commands):
            super().__init__(None, FLAGS)
            self.commands = commands
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setWindowTitle("Dave")
            screen = QtGui.QGuiApplication.primaryScreen()
            self.sprite = dave_stage.Sprite(time.perf_counter())
            self.setFixedSize(SW, SH)
            geo = screen.availableGeometry()
            self.rest = QtCore.QPoint(geo.right() - SW - 30, geo.bottom() - SH - 10)   # where he lives
            self.start = QtCore.QPoint(geo.right() + 20, geo.top() - 140)   # he arrives from off screen
            self.away = QtCore.QPoint(geo.right() + 80, geo.top() - 200)    # and leaves toward there
            self.move(self.start)
            self.phase, self.phase_t0 = "intro", time.perf_counter()        # intro -> live -> outro
            self.scale, self.landed, self.greeted, self.hello_sent = 0.4, False, False, False
            self.bubble = None
            self.bubble_rect = None
            self.pending, self.next_ok = [], 0.0
            self.speech_until = 0.0                    # while he is speaking, mood bubbles stay out of the way
            self.scene, self.now = None, time.perf_counter()
            self.press = self.drag = None
            self.mask_key = None
            self.failed = False
            self.timer = QtCore.QTimer(self)
            self.timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.timer.timeout.connect(self.tick)
            self.timer.start(8)                    # asks for ~120 fps; the screen decides the real rate

        # ----- asking the main program to speak (the voice engine lives there) -----
        def emit(self, event):
            try:
                print("@dave " + json.dumps(event), flush=True)
            except Exception:
                pass

        # ----- speech bubble -----
        def say(self, text, seconds=3.0):
            text = str(text)
            text = text if len(text) <= 70 else text[:67] + "..."
            self.bubble = {"text": text, "t0": time.perf_counter(), "dur": float(seconds)}

        def hush(self):
            b = self.bubble
            if b:
                b["dur"] = min(b["dur"], time.perf_counter() - b["t0"] + 0.2)

        # ----- events from the program that started Dave -----
        def handle(self, msg, now):
            cmd, arg = msg.get("cmd"), msg.get("arg")
            if DEBUG:
                print("[dave] got", json.dumps(msg), file=sys.stderr, flush=True)
            if cmd == "say" and isinstance(arg, dict):
                seconds = float(arg.get("seconds", 3.0))
                self.say(arg.get("text", ""), seconds)
                self.speech_until = now + seconds
            elif cmd in ("wake", "heard", "done"):
                self.sprite.handle(cmd, arg, now)
                if cmd == "wake":
                    self.hush()
                elif cmd == "heard" and now >= self.speech_until:
                    self.say(arg, 2.5)
                elif cmd == "done" and now >= self.speech_until:
                    self.say("Done!" if arg else "Oops, that didn't work.", 2.4)

        # ----- entrance and exit -----
        def begin_exit(self):
            if self.phase == "outro":
                return
            self.phase, self.phase_t0 = "outro", time.perf_counter()
            self.start = self.pos()                    # leave from wherever he is now
            self.pending = []
            self.hush()
            QtCore.QTimer.singleShot(int((FLY_OUT + 2) * 1000), QtWidgets.QApplication.quit)  # safety net

        def animate(self, now):
            """Moves the window and sets his size for the entrance / exit.
            Returns what his body should do, or None while he is just living on the desktop."""
            a = now - self.phase_t0
            if self.phase == "intro":
                if not self.hello_sent:                              # says hello while he flies in
                    self.hello_sent = True
                    self.emit({"speak": GREETING})
                if a < FLY_IN:                                       # swoops in, growing as he gets close
                    e = _ease_out(a / FLY_IN)
                    s = math.sin(math.pi * e)
                    self.move(int(self.start.x() + (self.rest.x() - self.start.x()) * e - 110 * s),
                              int(self.start.y() + (self.rest.y() - self.start.y()) * e - 50 * s))
                    self.scale = 0.4 + 0.6 * e
                    w = math.sin(a * 22) * 6
                    return {"pose_to": [0, 0, -0.3 * (1 - e), 140, 190 + w, 280, 190 - w],
                            "happy": False, "shadow": 0.0}
                if not self.landed:
                    self.landed = True
                    self.move(self.rest)
                    self.scale = 1.0
                st = a - FLY_IN                                      # lands with a hop and waves
                if st > 0.3 and not self.greeted:
                    self.greeted = True
                    if self.bubble is None:
                        self.say(GREETING, GREET_SECONDS)
                if st > WAVE:
                    self.phase = "live"
                    return None
                hop = abs(math.sin(st * 7)) * math.exp(-st * 1.6)
                wv = math.sin(st * 13)
                return {"pose_to": [0, -14 * hop, 0.04 * math.sin(st * 9) * math.exp(-st * 1.2),
                                    166, 228, 300 + 12 * wv, 140 + 3 * wv],
                        "happy": True, "shadow": min(1.0, st / 0.2)}
            if self.phase == "outro":                                # flies away, shrinking
                p = min(1.0, a / FLY_OUT)
                e = p * p                                            # slow take-off, then zooms off
                s = math.sin(math.pi * p)
                self.move(int(self.start.x() + (self.away.x() - self.start.x()) * e),
                          int(self.start.y() + (self.away.y() - self.start.y()) * e - 60 * s))
                self.scale = (1 - p) ** 1.5 + 0.01
                w = math.sin(a * 22) * 6
                if p >= 1.0:
                    QtWidgets.QApplication.quit()
                return {"pose_to": [0, 0, 0.3 * min(1.0, p * 3), 140, 190 + w, 280, 190 - w],
                        "happy": True, "shadow": 0.0}
            return None

        # ----- one frame -----
        def take_messages(self, now):
            """Moods wait until he has landed and each one is shown for a moment,
            so a quick wake -> heard -> done is never squashed into one jump."""
            while True:
                try:
                    msg = self.commands.get_nowait()
                except queue.Empty:
                    break
                cmd = msg.get("cmd")
                if cmd == "quit":
                    self.begin_exit()
                elif cmd == "mouth":                          # follows his voice: always right away
                    self.sprite.set_mouth(msg.get("arg") or 0.0)
                elif cmd == "level":
                    pass
                elif cmd == "hush":
                    self.hush()
                elif cmd == "say" and self.phase != "outro":     # in step with the voice: right away
                    self.handle(msg, now)
                else:
                    self.pending.append(msg)
            if self.phase == "live" and self.pending and now >= self.next_ok:
                msg = self.pending.pop(0)
                self.handle(msg, now)
                if msg.get("cmd") in ("wake", "heard", "done"):
                    self.next_ok = now + MIN_STATE_SECONDS

        def tick(self):
            try:
                now = time.perf_counter()
                self.take_messages(now)
                if self.bubble and now - self.bubble["t0"] > self.bubble["dur"]:
                    self.bubble = None
                self.scene = self.animate(now)
                self.now = now
                self.update_mask()
                self.update()
            except Exception:
                if not self.failed:              # show the first problem, then stay quiet
                    self.failed = True
                    import traceback
                    traceback.print_exc()

        def update_mask(self):
            """Linux: only the parts that are drawn catch mouse clicks, so the see-through
            rest of the window lets clicks reach the windows behind it. Windows does this
            by itself."""
            if sys.platform == "win32":
                return
            if self.phase != "live":
                rects = [QtCore.QRect(0, 0, SW, SH)]
            else:
                rects = [QtCore.QRect(84, 56, 214, 206)]                      # his body
                if self.sprite.bub > 0.03:
                    rects.append(QtCore.QRect(236, 30, 130, 96))              # thinking bubble
                if self.sprite.state == "ok":
                    rects.append(QtCore.QRect(14, 40, 352, 222))              # sparkles
                if self.bubble_rect is not None:
                    rects.append(self.bubble_rect)
            key = tuple((r.x(), r.y(), r.width(), r.height()) for r in rects)
            if key == self.mask_key:
                return
            self.mask_key = key
            region = QtGui.QRegion(rects[0])
            for r in rects[1:]:
                region = region.united(QtGui.QRegion(r))
            self.setMask(region)

        # ----- painting (Qt draws Dave directly: smooth, see-through, fast) -----
        def paintEvent(self, event):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
            p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Source)
            p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 0))     # start fully see-through
            p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
            p.translate(CENTER)                                  # shrink toward his middle
            p.scale(self.scale, self.scale)
            p.translate(-CENTER)
            try:
                self.sprite.draw(p, self.now, speaking=self.bubble is not None, scene=self.scene)
                self.paint_bubble(p)
            except Exception:
                if not self.failed:
                    self.failed = True
                    import traceback
                    traceback.print_exc()
            p.end()

        def paint_bubble(self, p):
            b = self.bubble
            self.bubble_rect = None
            if not b:
                return
            age = time.perf_counter() - b["t0"]
            g = _ease_back(age / 0.3) * min(1.0, (b["dur"] - age) / 0.2)
            if g <= 0.02:
                return
            font = QtGui.QFont()
            font.setPixelSize(14)
            font.setBold(True)
            p.setFont(font)
            fm = QtGui.QFontMetrics(font)
            box = fm.boundingRect(QtCore.QRect(0, 0, 150, 1000), TEXT_FLAGS, b["text"])
            w, h = max(60, box.width() + 28), box.height() + 20
            tx0, ty0 = dave_stage.TAIL_TIP                          # where the tail touches Dave
            tx, ty = tx0 + self.sprite.pose[0] * 0.5, ty0 + self.sprite.pose[1] * 0.5
            x, y = tx + 10, ty - 14 - h                             # bubble sits up and to the right
            self.bubble_rect = QtCore.QRect(int(tx0 - 6), int(ty0 - 40 - h), int(w + 28), int(h + 56))
            p.save()
            p.translate(tx, ty)                                     # pop in/out around the tail tip
            p.scale(g, g)
            p.translate(-tx, -ty)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor(240, 244, 252))
            p.drawRoundedRect(QtCore.QRectF(x, y, w, h), 18, 18)
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x + 14, y + h - 2),
                                           QtCore.QPointF(x + 36, y + h - 2),
                                           QtCore.QPointF(tx, ty)]))
            p.setPen(QtGui.QColor(40, 48, 70))
            opt = QtGui.QTextOption(Qt.AlignmentFlag.AlignCenter)
            opt.setWrapMode(QtGui.QTextOption.WrapMode.WordWrap)
            p.drawText(QtCore.QRectF(x + 8, y + 4, w - 16, h - 8), b["text"], opt)
            p.restore()

        # ----- mouse: drag Dave around, click him, right-click for the menu -----
        def mousePressEvent(self, event):
            if self.phase == "live" and event.button() == Qt.MouseButton.LeftButton:
                pos = event.globalPosition().toPoint()
                self.press = pos
                self.drag = pos - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, event):
            if self.drag is not None:
                self.move(event.globalPosition().toPoint() - self.drag)

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton and self.press is not None:
                moved = (event.globalPosition().toPoint() - self.press).manhattanLength()
                if moved < 5 and self.bubble is None:               # a click (not a drag), and he is not busy
                    import random
                    line = random.choice(CLICK_LINES)
                    self.say(line, 1.8)
                    self.emit({"speak": line})
            self.press = self.drag = None

        def contextMenuEvent(self, event):
            menu = QtWidgets.QMenu(self)
            hi = menu.addAction("Say hi")
            bye = menu.addAction("Send Dave home")
            chosen = menu.exec(event.globalPos())
            if chosen == hi:
                self.say(GREETING, GREET_SECONDS)
                self.emit({"speak": GREETING})
            elif chosen == bye:
                self.begin_exit()

    return DaveWindow


def _window_main():
    try:
        from PySide6 import QtWidgets
    except Exception:
        print("[ui_tts] Dave on the desktop needs PySide6:  python -m pip install PySide6")
        return
    commands = queue.Queue()

    def reader():                       # lines from the program that started Dave
        try:
            sys.stdin.reconfigure(encoding="utf-8")
        except Exception:
            pass
        try:
            for line in sys.stdin:
                try:
                    commands.put(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
        commands.put({"cmd": "quit"})   # the program ended: Dave goes home too

    app = QtWidgets.QApplication(sys.argv)
    window = _make_window_class()(commands)
    threading.Thread(target=reader, daemon=True).start()
    window.show()
    app.exec()


if __name__ == "__main__":
    _window_main()