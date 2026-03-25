from __future__ import annotations

from .base import LevelMap


class Capacity(LevelMap):
    """Two sources merge at one crossing; the crossing has two exits.

    The east exit is the shortest path to sink_east, but both sources
    together produce enough traffic to saturate it.  The southeast exit
    is longer but provides a second lane to sink_se — routing some
    traffic there maximises overall throughput.

    Viewport: width=320, height=180 (16:9).

    Street layout::

        src_north ──╮
                    crossing ──── (direct east) ──────────── sink_east
        src_south ──╯     ╲
                            ╲── (south-east) ── se_bend ──── sink_se

    Source ratio: src_north : src_south = 7 : 3

    Street indices:
        0  src_north → crossing   (no houses)
        1  src_south → crossing   (no houses)
        2  crossing  → sink_east  (direct east, shorter ≈ 240 units)
        3  crossing  → se_bend    (south-east leg, no houses)
        4  se_bend   → sink_se    (east leg, no houses)
    """

    def __init__(self) -> None:
        w = 320.0
        h = w * 9.0 / 16.0  # 180

        x_src = -10.0
        x_crossing = w * 0.25  # 80
        x_se_bend = w * 0.56  # ~179
        x_sink = w + 10.0  # 330

        y_north = h * 0.28  # ~50  – north source
        y_mid = 0.0  # horizontal centreline
        y_south = -h * 0.16  # ~-29 – south source (closer to centre)
        y_se = -h * 0.36  # ~-65 – south-east path

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int] | tuple[int, int, bool]] = []

        n_src_n = len(nodes)
        nodes.append((x_src, y_north))
        n_src_s = len(nodes)
        nodes.append((x_src, y_south))
        n_cross = len(nodes)
        nodes.append((x_crossing, y_mid))
        n_sink_e = len(nodes)
        nodes.append((x_sink, y_mid))
        n_se_bend = len(nodes)
        nodes.append((x_se_bend, y_se))
        n_sink_se = len(nodes)
        nodes.append((x_sink, y_se))

        streets.append((n_src_n, n_cross, True))  # 0 – north approach
        streets.append((n_src_s, n_cross, True))  # 1 – south approach
        streets.append((n_cross, n_sink_e, True))  # 2 – direct east (shorter)
        streets.append((n_cross, n_se_bend, True))  # 3 – south-east leg
        streets.append((n_se_bend, n_sink_se, True))  # 4 – east leg to SE sink

        super().__init__(
            nodes=nodes,
            streets=streets,
            width=w,
            seed=42,
            source_weights={0: 7.0, 1: 3.0},
        )

        # Decorative block between the two exit paths (wedge area)
        self.add_park(
            [
                (x_crossing + 10, y_mid - 8),
                (x_se_bend - 10, y_se + 8),
                (x_sink - 20, y_se + 8),
                (x_sink - 20, y_mid - 8),
            ]
        )

        self.add_cars(100, 20)
