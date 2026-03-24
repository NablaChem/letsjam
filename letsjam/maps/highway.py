from __future__ import annotations

from .base import LevelMap


class Highway(LevelMap):
    """Three parallel lanes running left to right.

    Viewport: width=320, height=180 (16:9).
    Origin at left-centre (x=0, y=0).

    Street layout (one street per lane):
        source (x=0, y) ──► sink (x=width, y)

    Street indices: lane 0 → 0 (y=+h*0.2), lane 1 → 1 (y=0), lane 2 → 2 (y=−h*0.2)
    """

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0
        half = h * 0.2

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        for y in [+half, 0.0, -half]:
            n_src = len(nodes)
            nodes.append((-10.0, y))
            n_sink = len(nodes)
            nodes.append((w + 10, y))
            streets.append((n_src, n_sink))

        super().__init__(nodes=nodes, streets=streets, width=w, seed=3)
        self.add_cars(6, 2)
