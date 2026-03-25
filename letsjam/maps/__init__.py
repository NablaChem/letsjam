"""
letsjam.maps – pre-built challenge maps.

Coordinate system
-----------------
x : 0 = left viewport edge, WIDTH = right viewport edge
y : 0 = vertical centre, positive UP, negative DOWN

Each map is a LevelMap subclass; instantiating it builds the full map.

Available maps
--------------
Highway    – three parallel lanes from left to right
MainStreet – single lane with a traffic light
SmallTown  – branching road network with a river and park
NoEscape   – single lane with a river obstacle
BabySteps  – L-shaped single lane

Usage
-----
>>> from letsjam.maps import Highway
>>> m = Highway()
"""

from .base import LevelMap, Decoration
from .baby_steps import BabySteps
from .capacity import Capacity
from .detour import Detour
from .highway import Highway
from .main_street import MainStreet
from .no_escape import NoEscape
from .small_town import SmallTown

__all__ = [
    "LevelMap",
    "Decoration",
    "BabySteps",
    "Capacity",
    "Detour",
    "Highway",
    "MainStreet",
    "NoEscape",
    "SmallTown",
]
