from __future__ import annotations

from .base import LevelMap


class Multipass(LevelMap):
    """A map where greedy fast-lane strategies can trap cars in a loop.

    Main path (y=0, horizontally centered):
        source ── [left] ──(FAST bypass)── [right] ── sink
                    ↘                          ↙
                    (SLOW entry)     (SLOW exit)
                       ↓                ↑
                    ── [base] ──
                     (triangle)

    The triangle loop can trap cars if they re-enter from the right.
    """

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0

        # Main horizontal path at y=0 (vertical center)
        y_main = 0.0
        y_base = -h * 0.35  # Triangle base offset downward

        x_src = -10.0
        x_left = w * 0.3
        x_right = w * 0.7
        x_sink = w + 10.0
        x_base = w * 0.5

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        # Main path nodes (all at y=0)
        n_src = len(nodes)
        nodes.append((x_src, y_main))

        n_left = len(nodes)
        nodes.append((x_left, y_main))

        n_right = len(nodes)
        nodes.append((x_right, y_main))

        n_sink = len(nodes)
        nodes.append((x_sink, y_main))

        # Triangle base (below main path)
        n_base = len(nodes)
        nodes.append((x_base, y_base))

        # Streets
        # Entry (slow): source → left
        streets.append((n_src, n_left))  # street 0

        # Fast bypass: left → right (avoids triangle entirely)
        streets.append((n_left, n_right))  # street 1

        # Exit (slow): right → sink
        streets.append((n_right, n_sink))  # street 2

        # Triangle loop (normal speed)
        streets.append((n_base, n_left))  # street 3 – enter triangle
        streets.append((n_right, n_base))  # street 5 – can re-enter from right

        super().__init__(nodes=nodes, streets=streets, width=w, seed=1)

        # Mark entry and exit as slow
        self.add_slow_street(0)  # source → left
        self.add_slow_street(2)  # right → sink

        self.add_cars(4, 0)
