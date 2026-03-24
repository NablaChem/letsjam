from __future__ import annotations

from .base import LevelMap


class NoEscape(LevelMap):
    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        for y in [0.0]:
            n_src = len(nodes)
            nodes.append((-10.0, y))
            n_left = len(nodes)
            nodes.append((w * 0.3, y))
            n_right = len(nodes)
            nodes.append((w * 0.7, y))
            n_sink = len(nodes)
            nodes.append((w + 10, y))
            streets.append((n_src, n_left))
            streets.append((n_left, n_right))
            streets.append((n_right, n_sink))

        super().__init__(nodes=nodes, streets=streets, width=w, seed=1)
        self.add_river(
            [
                (-20, -20),
                (40, 80),
                (200, -50),
                (400, 50),
            ],
            width=14,
        )
        self.add_park(
            [
                (-10, -200),
                (w, -200),
                (w, 200),
                (-10, 400),
            ]
        )
        self.add_cars(4, 0)
