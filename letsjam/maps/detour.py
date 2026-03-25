from __future__ import annotations

from .base import LevelMap


class Detour(LevelMap):
    """A map where the direct route passes through a slow zone; a triangular
    detour looping south is shorter but still faster overall.

    Viewport: width=320, height=180 (16:9).

    Street layout::

        [river runs east-west north of park]

        source ── [mid_left] ──(SLOW)── [mid_right] ── sink
                       ↘                    ↙
                          ── [bottom] ──
                         (triangle detour, south)

    Street indices:
        0  source   → mid_left          (normal)
        1  mid_left → mid_right         (SLOW – 160 units @ max 4 ≈ 40 frames)
        2  mid_right → sink             (normal)
        3  mid_left → bottom            (normal – ~102 units)
        4  bottom   → mid_right         (normal – ~102 units)

    Detour total ≈ 204 units @ speed 10 ≈ 20 frames  →  faster than the
    direct 160-unit slow road (≈ 40 frames).
    """

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0           # 180

        x_src    = -10.0
        x_mid_l  = w * 0.25          # 80
        x_mid_r  = w * 0.75          # 240
        x_sink   = w + 10.0
        x_bottom = w * 0.5           # 160 – apex of triangle

        y_mid    = 0.0
        y_bottom = -h * 0.35         # –63 – apex, just below park lower edge

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int] | tuple[int, int, bool]] = []

        n_src    = len(nodes);  nodes.append((x_src,    y_mid))
        n_mid_l  = len(nodes);  nodes.append((x_mid_l,  y_mid))
        n_mid_r  = len(nodes);  nodes.append((x_mid_r,  y_mid))
        n_sink   = len(nodes);  nodes.append((x_sink,   y_mid))
        n_bottom = len(nodes);  nodes.append((x_bottom, y_bottom))

        streets.append((n_src,    n_mid_l,  True))   # 0 – approach, no houses
        streets.append((n_mid_l,  n_mid_r))          # 1 – SLOW zone (houses only here)
        streets.append((n_mid_r,  n_sink,   True))   # 2 – exit, no houses
        streets.append((n_mid_l,  n_bottom, True))   # 3 – detour left leg, no houses
        streets.append((n_bottom, n_mid_r,  True))   # 4 – detour right leg, no houses

        super().__init__(nodes=nodes, streets=streets, width=w, seed=7)

        self.add_slow_street(1)

        # River running east-west north of the slow street
        ry = h * 0.38        # ~68
        self.add_river([
            (-20,       ry - 4),
            (40,        ry),
            (x_mid_l,   ry + 6),
            (w * 0.5,   ry + 2),
            (x_mid_r,   ry + 7),
            (w - 40,    ry + 1),
            (w + 20,    ry - 3),
        ], width=12)

        # Park fills the rectangle between the slow street (y=0) and the river
        self.add_park([
            (x_mid_l, y_mid),
            (x_mid_r, y_mid),
            (x_mid_r, ry),
            (x_mid_l, ry),
        ])

        self.add_cars(8, 2)
