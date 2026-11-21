"""Dave painted straight onto a see-through window with Qt's own painter.

dave_character.py decides how Dave looks and moves; this file only supplies the "pen"
that paints him with Qt. That gives

  * real see-through pixels (no halo, no black box edges),
  * smooth anti-aliased edges that stay sharp on any screen, including hi-dpi,
  * and very little work per frame, so the frame rate stays high.

Needs PySide6.
"""

import math

from PySide6 import QtCore, QtGui

from .dave_character import Character

# The part of Dave's drawing space that we cut out: him, his thinking bubble, the
# sparkles and his shadow. Everything else is left out.
X0, Y0, X1, Y1 = 20, 0, 440, 262
SW, SH = X1 - X0, Y1 - Y0

# Where the tip of a speech bubble's tail should touch Dave's head (inside the cut-out)
TAIL_TIP = (252 - X0, 126 - Y0)

_Qt = QtCore.Qt


def _color(c):
    return QtGui.QColor(*c)                    # (r, g, b) or (r, g, b, alpha)


class QtPen:
    """Draws Dave's shapes with Qt. One drawing unit = one window point; Qt scales that
    to the real screen by itself. set() moves / rotates / scales everything drawn after it."""

    def __init__(self, painter, org=(0, 0)):
        self.p, self.org = painter, org
        self.set()

    def set(self, ox=0.0, oy=0.0, rot=0.0, px=0.0, py=0.0, sx=1.0, sy=1.0):
        self.ox, self.oy, self.px, self.py = ox, oy, px, py
        self.sx, self.sy = sx, sy
        self.c, self.s = math.cos(rot), math.sin(rot)

    def pt(self, x, y):
        dx, dy = (x - self.px) * self.sx, (y - self.py) * self.sy
        return (self.px + dx * self.c - dy * self.s + self.ox - self.org[0],
                self.py + dx * self.s + dy * self.c + self.oy - self.org[1])

    def _fill(self, color):
        self.p.setPen(_Qt.PenStyle.NoPen)
        self.p.setBrush(_color(color))

    def _points(self, pts):
        return QtGui.QPolygonF([QtCore.QPointF(*self.pt(x, y)) for x, y in pts])

    def poly(self, pts, fill):
        self._fill(fill)
        self.p.drawPolygon(self._points(pts))

    def ell(self, cx, cy, rx, ry, fill, rot=0.0):
        n = int(max(32, min(120, max(rx, ry) * 1.8)))   # plenty of corners: smooth even when big
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
        pen = QtGui.QPen(_color(fill), w * abs(self.sx))
        pen.setCapStyle(_Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(_Qt.PenJoinStyle.RoundJoin)
        self.p.setPen(pen)
        self.p.setBrush(_Qt.BrushStyle.NoBrush)
        self.p.drawPolyline(self._points(pts))

    def oval(self, cx, cy, rx, ry, fill=None, outline=None, width=1.0):
        ox, oy = self.org
        self._fill(fill if fill is not None else (0, 0, 0, 0))
        self.p.drawEllipse(QtCore.QRectF(cx - rx - ox, cy - ry - oy, 2 * rx, 2 * ry))


class Sprite(Character):
    """Dave, painted with Qt. Call handle() for events and draw() for each frame."""

    def draw(self, painter, now, speaking=False, scene=None):
        return self.render(QtPen(painter, org=(X0, Y0)), now, speaking, scene)
