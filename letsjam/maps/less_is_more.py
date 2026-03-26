from __future__ import annotations

from .base import LevelMap


class LessIsMore(LevelMap):

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0  # 180

        x_s = -10.0
        x_mid = w * 0.5  # 160
        x_t = w + 10.0  # 330
        y_a = h * 0.39  #  ~70  (top)
        y_b = -h * 0.39  # ~-70  (bottom)

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int] | tuple[int, int, bool]] = []

        n_s = len(nodes)
        nodes.append((x_s, 0.0))
        n_a = len(nodes)
        nodes.append((x_mid, y_a))
        n_b = len(nodes)
        nodes.append((x_mid, y_b))
        n_t = len(nodes)
        nodes.append((x_t, 0.0))

        streets.append((n_s, n_a, True))  # 0 – S→A  fast  (source, no houses)
        streets.append((n_a, n_t))  # 1 – A→T  SLOW  (bottleneck, has houses)
        streets.append((n_s, n_b))  # 2 – S→B  SLOW  (bottleneck, has houses)
        streets.append((n_b, n_t, True))  # 3 – B→T  fast  (sink exit, no houses)
        streets.append((n_a, n_b, True))  # 4 – A→B  fast  (bridge, no houses)

        super().__init__(nodes=nodes, streets=streets, width=w, seed=17)

        self.add_slow_street(1)  # A→T — upper exit bottleneck
        self.add_slow_street(2)  # S→B — lower entry bottleneck

        # Park outside the diamond, alongside A→T slow lane (upper-right)
        # Points form a parallelogram offset outward from A→T by ~15–30 units.
        self.add_park(
            [
                (x_mid, y_b),
                (x_mid, -h),
                (x_s, -h),
                (x_s, 0),
            ]
        )
        self.add_park(
            [
                (x_mid, y_a),
                (x_mid, h),
                (x_t, h),
                (x_t, 0),
            ]
        )

        # River following two loops: small curl in lower-left, larger oval upper-right.

        self.add_river(
            [
                (w * 0.25, h * 0.6),  # enters lower-left
                (w * 0.15, h * 0.2),
                (w * 0.2, h * 0.0),
                (w * 0.6, h * 0.2),
                (w * 0.7, -h * 0.1),
                (w * 0.9, -h * 0.6),
            ],
            width=20,
        )

        self.add_cars(50, 0)
