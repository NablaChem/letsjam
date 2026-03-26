"""
letsjam – traffic simulation visualiser for Jupyter notebooks.

Quick start
-----------
>>> from letsjam.maps import SmallTown
>>> from letsjam.propagate import run_simulation
>>> from letsjam import TrafficWidget
>>>
>>> m = SmallTown()
>>>
>>> traj = run_simulation(m, n_frames=240, car_drive=..., car_turn=..., traffic_light=...)
>>> TrafficWidget.from_simulation(m, traj)
"""

from .maps.base import Decoration, LevelMap
from .maps import Highway
from .propagate import run_strategy_on_all_maps
from .simulation import DISABLED, Trajectory, unpack_trajectory
from .widget import TrafficWidget

__all__ = [
    "LevelMap",
    "Decoration",
    "Highway",
    "Trajectory",
    "TrafficWidget",
    "DISABLED",
    "unpack_trajectory",
    "run_strategy_on_all_maps",
]
