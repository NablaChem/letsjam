"""
Map data structures for letsjam.

A LevelMap contains:
  - nodes:       list of (x, y) crossing centres
  - streets:     list of (from_node_idx, to_node_idx) directed edges;
                 street_id = index in this list
  - decorations: optional visual elements (parks, rivers)
  - car_types:   per-car type array (0 = car, 1 = truck)
  - car_length / truck_length: world-unit lengths used for rendering
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Decoration:
    type: Literal["park", "river"]
    # park  → polygon  (list of [x, y])
    # river → polyline (list of [x, y]) + width
    points: list[list[float]]
    width: float = 8.0          # only used for rivers

    def to_dict(self) -> dict:
        d: dict = {"type": self.type, "points": self.points}
        if self.type == "river":
            d["width"] = self.width
        return d


class LevelMap:
    """Base class for all letsjam levels.

    Subclasses set up nodes/streets in __init__, call super().__init__(),
    then add decorations and vehicles.

    Example subclass::

        class MyLevel(LevelMap):
            def __init__(self) -> None:
                nodes = [(0, 0), (200, 0)]
                streets = [(0, 1)]
                super().__init__(nodes=nodes, streets=streets, width=200, seed=1)
                self.add_cars(n_cars=3)
    """

    def __init__(
        self,
        nodes: list[tuple[float, float]],
        streets: list[tuple[int, int]],
        width: float = 0.0,
        seed: int = 0,
        decorations: list[Decoration] | None = None,
        car_types: list[int] | None = None,
        car_length: float = 4.0,
        truck_length: float = 8.0,
        source_weights: dict[int, float] | None = None,
    ) -> None:
        self.nodes = list(nodes)
        self.streets = list(streets)
        self.width = width
        self.seed = seed
        self.decorations: list[Decoration] = decorations if decorations is not None else []
        self.car_types: list[int] = car_types if car_types is not None else []
        self.car_length = car_length
        self.truck_length = truck_length
        self.source_weights: dict[int, float] = source_weights if source_weights is not None else {}

    @property
    def height(self) -> float:
        """Viewport height inferred from width at a fixed 16:9 aspect ratio."""
        return self.width * 9.0 / 16.0

    # ------------------------------------------------------------------
    # geometry helpers
    # ------------------------------------------------------------------

    def street_length(self, street_id: int) -> float:
        """Euclidean length of a street."""
        fi, ti = self.streets[street_id]
        fx, fy = self.nodes[fi]
        tx, ty = self.nodes[ti]
        return math.hypot(tx - fx, ty - fy)

    def street_direction(self, street_id: int) -> tuple[float, float]:
        """Unit vector along a street (for car heading)."""
        fi, ti = self.streets[street_id]
        fx, fy = self.nodes[fi]
        tx, ty = self.nodes[ti]
        length = math.hypot(tx - fx, ty - fy)
        if length == 0:
            return (1.0, 0.0)
        return ((tx - fx) / length, (ty - fy) / length)

    def world_pos(self, street_id: int, dist: float) -> tuple[float, float]:
        """World (x, y) for a car at (street_id, dist)."""
        fi, ti = self.streets[street_id]
        fx, fy = self.nodes[fi]
        tx, ty = self.nodes[ti]
        length = math.hypot(tx - fx, ty - fy)
        t = dist / length if length > 0 else 0.0
        return (fx + (tx - fx) * t, fy + (ty - fy) * t)

    # ------------------------------------------------------------------
    # car / truck helpers
    # ------------------------------------------------------------------

    @property
    def n_cars(self) -> int:
        return len(self.car_types)

    def add_cars(self, n_cars: int = 0, n_trucks: int = 0) -> None:
        """Append n_cars cars (type 0) and n_trucks trucks (type 1)."""
        self.car_types.extend([0] * n_cars)
        self.car_types.extend([1] * n_trucks)

    def car_visual_length(self, car_idx: int) -> float:
        return self.truck_length if self.car_types[car_idx] == 1 else self.car_length

    # ------------------------------------------------------------------
    # decoration helpers
    # ------------------------------------------------------------------

    def add_park(self, polygon: list[tuple[float, float]]) -> None:
        self.decorations.append(
            Decoration(type="park", points=[[x, y] for x, y in polygon])
        )

    def add_river(
        self, polyline: list[tuple[float, float]], width: float = 8.0
    ) -> None:
        self.decorations.append(
            Decoration(type="river", points=[[x, y] for x, y in polyline], width=width)
        )

    # ------------------------------------------------------------------
    # serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to the JSON structure consumed by the JS widget."""
        return {
            "nodes":        [[x, y] for x, y in self.nodes],
            "streets":      [list(s) for s in self.streets],
            "decorations":  [d.to_dict() for d in self.decorations],
            "car_types":    list(self.car_types),
            "car_length":   self.car_length,
            "truck_length": self.truck_length,
            "width":        self.width,
        }
