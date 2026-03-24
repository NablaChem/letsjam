"""
Map data structures for letsjam.

A Map contains:
  - nodes:       list of (x, y) crossing centres
  - streets:     list of (from_node_idx, to_node_idx) directed edges;
                 street_id = index in this list
  - decorations: optional visual elements (parks, rivers)
  - car_types:   per-car type array (0 = car, 1 = truck)
  - car_length / truck_length: world-unit lengths used for rendering

Example
-------
>>> m = Map(
...     nodes=[(0, 0), (100, 0), (100, 100)],
...     streets=[(0, 1), (1, 2), (2, 0)],
... )
>>> m.add_cars(n_cars=5, n_trucks=2)
>>> m.street_length(0)
100.0
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


@dataclass
class Map:
    nodes:        list[tuple[float, float]]
    streets:      list[tuple[int, int]]
    decorations:  list[Decoration] = field(default_factory=list)
    car_types:    list[int]        = field(default_factory=list)  # 0=car 1=truck
    car_length:   float            = 4.0
    truck_length: float            = 8.0
    # Viewport width in world units.  Height is always width * 9/16.
    # When 0 the widget falls back to auto-fitting from node bounds.
    width:        float            = 0.0
    # Relative spawn weights keyed by street_id.  Missing entries default to 1.
    # A source with weight 2 receives twice as many initial cars as one with weight 1.
    source_weights: dict[int, float] = field(default_factory=dict)

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
