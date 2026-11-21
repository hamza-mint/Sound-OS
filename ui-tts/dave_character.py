"""Dave himself: his looks, his moods and his movement.

No windows, no Qt and no Pillow in here. This file only decides what Dave looks like at
each moment and asks a "pen" to draw it (see dave_stage.py for the pen that paints with Qt).

Moods:  idle (head bobs, blinks, looks around)   listening / heard (thinking, thought bubble)
        ok (happy hop, sparkles)                 fail (sad, tear, little shake)
While he speaks his mouth follows the voice: call set_mouth(level) with 0.0 - 1.0.
"""

import math
import time

# ---------- Settings (tweak freely) ----------
GREETING = "Hi, I'm Dave!\nHow can I help?"   # speech bubble when he arrives ("" = off)
GREET_SECONDS = 4.0          # how long it stays
RESULT_SECONDS = 2.0         # how long the happy / sad mood lasts

# ---------- Colors ----------
ACCENT = (110, 168, 255)
GREEN = (52, 199, 89)
RED = (255, 59, 48)
WHITE = (255, 255, 255)
GOLD = (255, 214, 10)
BODY = (228, 234, 246)
BODY2 = (172, 185, 210)
FACE = (27, 32, 44)
EYE = (127, 227, 255)
BLUSH = (114, 201, 237)
TALK_MOUTH_OUTER = (16, 40, 63)
TALK_MOUTH_INNER = (50, 155, 203)

HX, HY = 210, 150            # head center in Dave's own drawing space


# ---------- small helpers ----------
def _mix(a, b, p):
    return tuple(int(a[i] + (b[i] - a[i]) * p) for i in range(3))


def ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_back(p):
    """Overshoots a little, then settles: good for things that pop in."""
    p = max(0.0, min(1.0, p)) - 1
    return 1 + 2.70158 * p ** 3 + 1.70158 * p ** 2


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


class Character:
    """Dave's mood and movement. Call handle() for events, set_mouth() while he talks,
    and render(pen, now) once per frame."""

    def __init__(self, now):
        self.t0 = self.state_t = now
        self.state = "idle"
        self.heard = ""
        self.last_t, self.dt = None, 1 / 60
        self.bub = 0.0                                   # thought bubble size 0..1
        self.talk, self.talk_target, self.talk_t = 0.0, 0.0, -10.0     # how open his mouth is
        # smoothed pose: head x, head y, head tilt, left hand xy, right hand xy
        self.pose = [0.0, 0.0, 0.0, 158.0, 226.0, 262.0, 226.0]

    def handle(self, cmd, arg, now):
        if cmd == "wake":
            self.state, self.state_t, self.heard = "listening", now, ""
        elif cmd == "heard":
            self.state, self.state_t, self.heard = "heard", now, str(arg)
        elif cmd == "done":
            self.state, self.state_t = ("ok" if arg else "fail"), now

    def set_mouth(self, level):
        """How open his mouth should be, 0.0 (closed) - 1.0. Send it again at least every
        0.4 s while he talks; if the updates stop, his mouth closes by itself."""
        self.talk_target = max(0.0, min(1.0, float(level)))
        self.talk_t = time.perf_counter()

    def render(self, pen, now, speaking=False, scene=None):
        """Moves time forward and draws Dave with `pen`. Returns his state.

        speaking=True hides the thinking bubble, because a speech bubble is in its place.
        scene (optional) takes over his body for the entrance / exit: a dict with
        pose_to (arms, head), happy (smiling face) and shadow (0 = flying, 1 = on the ground).
        """
        scene = scene or {}
        self.dt = min(0.1, max(0.001, now - self.last_t)) if self.last_t is not None else 1 / 60
        self.last_t = now
        t = now - self.t0
        st = now - self.state_t
        state = self.state
        if state in ("ok", "fail") and st > RESULT_SECONDS:
            self.state, self.state_t, self.heard = "idle", now, ""
            state, st = "idle", 0.0
        thinking = state in ("listening", "heard")
        accent = GREEN if state == "ok" else RED if state == "fail" else ACCENT

        dx = 0.0                                             # little shake on failure
        if state == "fail" and st > 0.3:
            k = st - 0.3
            if k < 0.6:
                dx = 9 * math.sin(k * 45) * (1 - k / 0.6)

        target = 1.0 if (thinking and not speaking) else 0.0
        self.bub += (target - self.bub) * (1 - math.exp(-self.dt * 7.5))

        if time.perf_counter() - self.talk_t > 0.4:          # no news from the voice: close up
            self.talk_target = 0.0
        self.talk += (self.talk_target - self.talk) * (1 - math.exp(-self.dt * 30))

        self._robot(pen, state, thinking, t, st, dx, accent,
                    shadow=scene.get("shadow", 1.0), pose_to=scene.get("pose_to"),
                    happy=scene.get("happy", False), sparkles=not scene, talk=self.talk)
        return state

    def _robot(self, pen, state, thinking, t, st, dx, accent,
               off=(0.0, 0.0), shadow=1.0, pose_to=None, happy=False, sparkles=True, talk=0.0):
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
            e = ease_out(st / 0.5)
            tg = [0, 8 * e + 1.5 * math.sin(t * 2), -0.14 * e, 166, 238, 254, 238]
        else:
            tg = [5 * math.sin(t * 0.9), 3 * math.sin(t * 1.7), 0.10 * math.sin(t * 1.3),
                  158 + 2 * sw, 226, 262 - 2 * sw, 226]
        if pose_to is not None:
            tg = pose_to
        tg = list(tg)
        tg[1] -= 2.0 * talk                                  # a little nod while he talks
        f = 1 - math.exp(-self.dt * (20.8 if pose_to is not None else 10.7))
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
        pulse = min(1.0, 0.6 + 0.4 * math.sin(t * (7 if thinking else 3)) + 0.5 * talk)
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
        if talk > 0.04:                                         # talking: opens with his voice
            ry = 2.0 + 9.5 * talk
            rx = 6.0 + 5.0 * talk
            cy = 13.5 + 3.5 * talk
            pen.ell(0, cy, rx, ry, TALK_MOUTH_OUTER)
            if talk > 0.25:
                pen.ell(0, cy + ry * 0.45, rx * 0.6, ry * 0.45, TALK_MOUTH_INNER)
        elif face_ok:
            pen.poly(_arc(0, 8, 11, 12, 0, math.pi), TALK_MOUTH_INNER)
        elif fail:
            pen.stroke(_arc(0, 24, 9, 7, math.pi * 1.15, math.pi * 1.85), 3.2, EYE)
        elif thinking:
            pen.ell(lx * 0.5, 15, 3.6, 4.2 + 0.8 * math.sin(t * 5), EYE)
        else:
            pen.stroke(_arc(0, 9, 9, 6.5, math.pi * 0.2, math.pi * 0.8), 3.2, EYE)

        # thought bubble while listening / working
        if self.bub > 0.03:
            sc = ease_out(self.bub)
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
                rad = 80 + 55 * ease_out(life)
                col = (GREEN if i % 2 else GOLD) + (int(255 * (1 - life * life)),)
                pen.poly(_star(HX + math.cos(a) * rad * 1.25, HY + 10 + math.sin(a) * rad * 0.8,
                               4 + 7 * (1 - life)), col)
