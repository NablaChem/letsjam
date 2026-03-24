from __future__ import annotations

from .base import LevelMap


class MainStreet(LevelMap):
    """A single lane with a traffic light in the middle.

    Viewport: width=320, height=180 (16:9).
    Origin at left-centre (x=0, y=0).

    Street layout:
        source (x=0, y=0) ──► traffic light (x=width/2, y=0) ──► sink (x=width, y=0)
    """

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        n_src = len(nodes)
        nodes.append((-10.0, 0.0))
        n_light = len(nodes)
        nodes.append((w * 0.6, 0.2 * h))
        n_sink = len(nodes)
        nodes.append((w + 10, 0.0))
        streets.append((n_src, n_light))
        streets.append((n_light, n_sink))

        super().__init__(nodes=nodes, streets=streets, width=w, seed=4)
        self.add_cars(4, 1)
