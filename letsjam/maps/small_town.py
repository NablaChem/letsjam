from __future__ import annotations

from .base import LevelMap


class SmallTown(LevelMap):
    def __init__(self) -> None:
        w = 220.0
        h = w * 9.0 / 16.0

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        n_src = len(nodes)
        nodes.append((-10.0, 0.2 * h))
        n_top_left = len(nodes)
        nodes.append((w * 0.3, 0.2 * h))
        n_top_right = len(nodes)
        nodes.append((w * 0.7, 0.2 * h))
        n_bottom_left = len(nodes)
        nodes.append((w * 0.3, -0.2 * h))
        n_bottom_right = len(nodes)
        nodes.append((w * 0.7, -0.2 * h))
        n_sink = len(nodes)
        nodes.append((w + 10, -0.2 * h))
        streets.append((n_src, n_top_left))
        streets.append((n_top_left, n_top_right))
        streets.append((n_top_left, n_bottom_left))
        streets.append((n_top_right, n_bottom_right))
        streets.append((n_bottom_left, n_bottom_right))
        streets.append((n_bottom_right, n_sink))

        super().__init__(nodes=nodes, streets=streets, width=w, seed=5)
        self.add_river(
            [
                (-20, 50),
                (30, 53),
                (80, 49),
                (160, 52),
                (210, 51),
                (216, 22),
                (218, 0),
                (216, -22),
                (210, -51),
                (160, -52),
                (80, -49),
                (30, -53),
                (-20, -50),
            ],
            width=14,
        )
        self.add_park(
            [
                (72, -19),
                (148, -19),
                (148, 19),
                (72, 19),
            ]
        )
        self.add_cars(6, 2)
