"""
letsjam.maps – pre-built challenge maps.

Coordinate system
-----------------
x : 0 = left viewport edge, WIDTH = right viewport edge
y : 0 = vertical centre, positive UP, negative DOWN

Each challenge is a subclass of ChallengeMap.  Call .build() to get a fresh
Map instance ready for cars to be added.

Available maps
--------------
Highway   – three parallel lanes from left to right

Usage
-----
>>> from letsjam.maps import Highway
>>> m = Highway.build()
>>> m.add_cars(n_cars=6)
"""

from __future__ import annotations

from typing import ClassVar

from ..graph import Map


class ChallengeMap:
    """Base class for all challenge maps.

    Subclasses set ``WIDTH`` (world units) and override ``build()``.
    ``height()`` is derived automatically at a fixed 16:9 ratio.
    The coordinate origin is the left-centre of the viewport:
    x ∈ [0, WIDTH], y ∈ [-height/2, +height/2].
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    WIDTH: ClassVar[float] = 0.0

    @classmethod
    def height(cls) -> float:
        """Viewport height inferred from WIDTH at a fixed 16:9 aspect ratio."""
        return cls.WIDTH * 9.0 / 16.0

    @classmethod
    def build(cls) -> Map:
        """Return a fresh Map for this challenge (no cars added yet)."""
        raise NotImplementedError


class NoEscape(ChallengeMap):
    name = "no_escape"
    WIDTH = 320.0

    @classmethod
    def build(cls) -> Map:
        w = cls.WIDTH

        lane_ys = [0.0]

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        for y in lane_ys:
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

        m = Map(nodes=nodes, streets=streets, width=w)
        m.add_river(
            [
                (-20, -20),
                (40, 80),
                (200, -50),
                (400, 50),
            ],
            width=14,
        )

        m.add_park(
            [
                (-10, -200),
                (w, -200),
                (w, 200),
                (-10, 400),
            ]
        )
        return m


class BabySteps(ChallengeMap):
    name = "baby_steps"
    WIDTH = 320.0

    @classmethod
    def build(cls) -> Map:
        w = cls.WIDTH

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        n_src = len(nodes)
        nodes.append((-10.0, 50))
        n_left = len(nodes)
        nodes.append((w * 0.3, 50))
        n_right = len(nodes)
        nodes.append((w * 0.3, -50))
        n_sink = len(nodes)
        nodes.append((w + 10, -50))
        streets.append((n_src, n_left))
        streets.append((n_left, n_right))
        streets.append((n_right, n_sink))

        m = Map(nodes=nodes, streets=streets, width=w)
        m.add_river(
            [
                (-20, -20),
                (40, 80),
                (200, -50),
                (400, 50),
            ],
            width=14,
        )

        m.add_park(
            [
                (-10, -200),
                (w, -200),
                (w, 200),
                (-10, 400),
            ]
        )
        return m


class Highway(ChallengeMap):
    """Three parallel lanes running left to right.

    Viewport: WIDTH=320, height=180 (16:9).
    Origin at left-centre (x=0, y=0).

    Street layout (one street per lane):
        source (x=0, y) ──► sink (x=WIDTH, y)

    Street indices: lane 0 → 0 (y=+h*0.2), lane 1 → 1 (y=0), lane 2 → 2 (y=−h*0.2)
    """

    name = "highway"
    description = (
        "Three parallel lanes running left to right. "
        "Keep traffic flowing without rear-end collisions."
    )
    WIDTH = 320.0

    @classmethod
    def build(cls) -> Map:
        w = cls.WIDTH
        h = cls.height()  # 180.0
        half = h * 0.2  # lane offset from centre

        lane_ys = [+half, 0.0, -half]

        nodes: list[tuple[float, float]] = []
        streets: list[tuple[int, int]] = []

        for y in lane_ys:
            n_src = len(nodes)
            nodes.append((-10.0, y))
            n_sink = len(nodes)
            nodes.append((w + 10, y))
            streets.append((n_src, n_sink))

        return Map(nodes=nodes, streets=streets, width=w)


class MainStreet(ChallengeMap):
    """A single lane with a traffic light in the middle.

    Viewport: WIDTH=320, height=180 (16:9).
    Origin at left-centre (x=0, y=0).

    Street layout:
        source (x=0, y=0) ──► traffic light (x=WIDTH/2, y=0) ──► sink (x=WIDTH, y=0)

    Street indices: lane 0 → 0 (y=0)
    """

    name = "main_street"
    description = (
        "A single lane with a traffic light in the middle. "
        "Keep traffic flowing without rear-end collisions."
    )
    WIDTH = 320.0

    @classmethod
    def build(cls) -> Map:
        w = cls.WIDTH
        h = cls.height()  # 180.0

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

        return Map(nodes=nodes, streets=streets, width=w)


class SmallTown(ChallengeMap):
    WIDTH = 220.0

    @classmethod
    def build(cls) -> Map:
        w = cls.WIDTH
        h = cls.height()  # 180.0

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

        m = Map(nodes=nodes, streets=streets, width=w)

        # River winding around the perimeter (U-shape, top → right → bottom)
        m.add_river(
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

        # Park in the centre block formed by the four intersections
        m.add_park(
            [
                (72, -19),
                (148, -19),
                (148, 19),
                (72, 19),
            ]
        )

        return m
