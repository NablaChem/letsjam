"""
anywidget-based traffic visualisation widget for letsjam.

Usage
-----
>>> from letsjam import Map, Trajectory, TrafficWidget
>>>
>>> m = Map(nodes=[(0,0),(200,0),(200,200)], streets=[(0,1),(1,2),(2,0)])
>>> m.add_cars(n_cars=3, n_trucks=1)
>>>
>>> traj = Trajectory(m)
>>> for step in range(60):
...     states = [
...         (0, step * 2.0),   # car 0
...         (1, step * 1.5),   # car 1
...         (2, step * 1.8),   # car 2
...         (0, step * 0.8),   # truck 0
...     ]
...     traj.append(states)
>>>
>>> widget = TrafficWidget.from_simulation(m, traj)
>>> widget   # display in notebook
"""

from __future__ import annotations

import pathlib

import anywidget
import traitlets

from .graph import Map
from .simulation import Trajectory

_static = pathlib.Path(__file__).parent / "static"


def _build_esm() -> str:
    """Concatenate vendored pixi.min.js with widget.js into one ES module.

    pixi.min.js (cdnjs browser build) declares `var PIXI = function(_){...}({})`.
    We wrap it in a try/catch IIFE so that:
      - any initialization error is caught and surfaced rather than silently leaving
        PIXI undefined
      - the result is assigned to a module-level `let PIXI` that widget.js can use
      - `var PIXI` inside the IIFE is function-scoped and returned explicitly
    """
    pixi   = (_static / "pixi.min.js").read_text(encoding="utf-8")
    widget = (_static / "widget.js").read_text(encoding="utf-8")
    pixi_block = (
        "let PIXI;\n"
        "try {\n"
        "  PIXI = (() => {\n"
        + pixi + "\n"
        "  return PIXI;\n"
        "  })();\n"
        "} catch (_pixiErr) {\n"
        "  console.error('[letsjam] PixiJS failed to initialise:', _pixiErr);\n"
        "}\n"
    )
    return pixi_block + widget


class TrafficWidget(anywidget.AnyWidget):
    """
    Jupyter widget that visualises a letsjam traffic simulation.

    Traitlets (all synced to JS)
    ----------------------------
    map_data   : dict   – serialised Map (nodes, streets, decorations, …)
    trajectory : bytes  – packed binary trajectory blob
    n_frames   : int    – number of frames in the trajectory
    n_cars     : int    – number of cars tracked
    """

    _esm = _build_esm()
    _css = _static / "widget.css"

    map_data   = traitlets.Dict({}).tag(sync=True)
    trajectory = traitlets.Bytes(b"").tag(sync=True)
    lights     = traitlets.Bytes(b"").tag(sync=True)
    n_frames   = traitlets.Int(0).tag(sync=True)
    n_cars     = traitlets.Int(0).tag(sync=True)

    # ------------------------------------------------------------------
    # convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_simulation(
        cls,
        map_: Map,
        traj: Trajectory,
    ) -> "TrafficWidget":
        """
        Build a widget from a completed simulation.

        Parameters
        ----------
        map_ :
            The map used for the simulation.
        traj :
            A Trajectory whose append() calls are all done.
        """
        if traj.n_frames == 0:
            raise ValueError("Trajectory has no frames.")

        return cls(
            map_data   = map_.to_dict(),
            trajectory = traj.to_bytes(),
            lights     = traj.lights_to_bytes(),
            n_frames   = traj.n_frames,
            n_cars     = traj.n_cars,
        )

    # ------------------------------------------------------------------
    # live update helpers (e.g. re-run simulation and push new trajectory)
    # ------------------------------------------------------------------

    def update_trajectory(self, traj: Trajectory) -> None:
        """Replace the trajectory without rebuilding the static scene."""
        self.n_frames   = traj.n_frames
        self.n_cars     = traj.n_cars
        self.trajectory = traj.to_bytes()
        self.lights     = traj.lights_to_bytes()

    def update_map(self, map_: Map) -> None:
        """Replace the map (rebuilds the full scene in JS)."""
        self.map_data = map_.to_dict()

    def update_simulation(self, map_: Map, traj: Trajectory) -> None:
        """Replace both map and trajectory atomically (single JS rebuild)."""
        # set map last so JS rebuild sees the new trajectory already in place
        self.n_frames   = traj.n_frames
        self.n_cars     = traj.n_cars
        self.trajectory = traj.to_bytes()
        self.lights     = traj.lights_to_bytes()
        self.map_data   = map_.to_dict()
