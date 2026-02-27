"""
Trajectory building and binary serialisation for letsjam.

Binary format
-------------
Header  (8 bytes):  int32 n_frames  |  int32 n_cars
Payload (n_frames × n_cars × 8 bytes):
    per car per frame:  int32 edge_id  |  float32 dist
    edge_id == -1  →  car is disabled / off-map (dist ignored)

All values little-endian.

Example
-------
>>> from letsjam.graph import Map
>>> from letsjam.simulation import Trajectory
>>>
>>> m = Map(nodes=[(0,0),(100,0)], streets=[(0,1)])
>>> m.add_cars(n_cars=3)
>>>
>>> traj = Trajectory(m)
>>> for step in range(10):
...     states = [(0, step * 5.0), (0, step * 3.0), (-1, 0.0)]
...     traj.append(states)
>>> widget_bytes = traj.to_bytes()
"""

from __future__ import annotations

import struct

import numpy as np

from .graph import Map


# dtype for one (edge_id, dist) cell — naturally aligned, 8 bytes
_CELL_DTYPE = np.dtype([("edge_id", "<i4"), ("dist", "<f4")])

# sentinel value for a disabled car
DISABLED: int = -1


class Trajectory:
    """
    Accumulates per-frame car states and serialises them to bytes.

    Parameters
    ----------
    map_:
        The Map this trajectory belongs to.  Used for n_cars validation.
    """

    def __init__(self, map_: Map) -> None:
        self._map = map_
        self._frames: list[np.ndarray] = []   # each entry: 1D array of _CELL_DTYPE, shape (n_cars,)
        self._light_frames: list[list[int]] = []  # per frame: light_green index per node

    # ------------------------------------------------------------------
    # building
    # ------------------------------------------------------------------

    @property
    def n_frames(self) -> int:
        return len(self._frames)

    @property
    def n_cars(self) -> int:
        return self._map.n_cars

    def append(self, states: list[tuple[int, float]]) -> None:
        """
        Add one frame.

        Parameters
        ----------
        states:
            List of (edge_id, dist) for each car, in car-index order.
            Use edge_id = -1 (DISABLED) for cars not on the map.
            Length must equal map_.n_cars.
        """
        n = self._map.n_cars
        if len(states) != n:
            raise ValueError(
                f"Expected {n} car states, got {len(states)}. "
                "Make sure map_.add_cars() was called before building the trajectory."
            )
        frame = np.empty(n, dtype=_CELL_DTYPE)
        for i, (eid, dist) in enumerate(states):
            frame[i]["edge_id"] = eid
            frame[i]["dist"]    = dist
        self._frames.append(frame)

    def append_lights(self, light_green: list[int]) -> None:
        """Record per-node traffic light state for the current frame.

        Parameters
        ----------
        light_green:
            One int per node: the inbound-street index that is green, or -1
            if all lights at that node are red.
        """
        self._light_frames.append(list(light_green))

    def lights_to_bytes(self) -> bytes:
        """Serialise light state to binary.

        Format: 8-byte header (int32 n_frames, int32 n_nodes) followed by
        n_frames × n_nodes int8 values (row-major).  Returns b"" if no light
        frames have been recorded.
        """
        if not self._light_frames:
            return b""
        arr = np.array(self._light_frames, dtype=np.int8)
        n_frames, n_nodes = arr.shape
        return struct.pack("<ii", n_frames, n_nodes) + arr.tobytes()

    def append_dict(self, states: dict[int, tuple[int, float]]) -> None:
        """
        Add one frame from a dict mapping car_idx → (edge_id, dist).
        Cars absent from the dict are marked disabled.
        """
        n = self._map.n_cars
        frame_list: list[tuple[int, float]] = [(DISABLED, 0.0)] * n
        for car_idx, (eid, dist) in states.items():
            frame_list[car_idx] = (eid, dist)
        self.append(frame_list)

    # ------------------------------------------------------------------
    # serialisation
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """
        Serialise to the binary format consumed by the JS widget.

        Returns
        -------
        bytes
            8-byte header + payload as little-endian packed binary.
        """
        if not self._frames:
            raise ValueError("Trajectory is empty — append at least one frame.")

        header = struct.pack("<ii", self.n_frames, self.n_cars)
        payload = np.stack(self._frames, axis=0)   # shape (n_frames, n_cars)
        return header + payload.tobytes()

    # ------------------------------------------------------------------
    # introspection helpers
    # ------------------------------------------------------------------

    def get_frame(self, frame_idx: int) -> list[tuple[int, float]]:
        """Return frame as list of (edge_id, dist) tuples."""
        f = self._frames[frame_idx]
        return [(int(f[i]["edge_id"]), float(f[i]["dist"])) for i in range(self.n_cars)]

    def __repr__(self) -> str:
        return (
            f"Trajectory(n_frames={self.n_frames}, n_cars={self.n_cars})"
        )


def unpack_trajectory(data: bytes) -> tuple[int, int, np.ndarray]:
    """
    Unpack a binary trajectory blob (for testing / introspection).

    Returns
    -------
    n_frames, n_cars, array
        array has shape (n_frames, n_cars) and dtype [('edge_id','<i4'),('dist','<f4')]
    """
    n_frames, n_cars = struct.unpack_from("<ii", data, 0)
    arr = np.frombuffer(data, dtype=_CELL_DTYPE, offset=8)
    return n_frames, n_cars, arr.reshape(n_frames, n_cars)
