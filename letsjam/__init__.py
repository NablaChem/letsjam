"""
letsjam – traffic simulation visualiser for Jupyter notebooks.

Quick start
-----------
>>> from letsjam import Map, Trajectory, TrafficWidget
>>>
>>> # 1. define the map
>>> m = Map(
...     nodes=[(0, 0), (200, 0), (200, 200), (0, 200)],
...     streets=[(0, 1), (1, 2), (2, 3), (3, 0)],
... )
>>> m.add_cars(n_cars=4, n_trucks=1)
>>>
>>> # 2. build a trajectory
>>> traj = Trajectory(m)
>>> for step in range(100):
...     traj.append([
...         (i % 4, (step * 2.0 + i * 50) % m.street_length(i % 4))
...         for i in range(m.n_cars)
...     ])
>>>
>>> # 3. display
>>> TrafficWidget.from_simulation(m, traj)
"""

from .graph import Decoration, Map
from .maps import ChallengeMap, Highway
from .simulation import DISABLED, Trajectory, unpack_trajectory
from .widget import TrafficWidget

__all__ = [
    "Map",
    "Decoration",
    "ChallengeMap",
    "Highway",
    "Trajectory",
    "TrafficWidget",
    "DISABLED",
    "unpack_trajectory",
]
