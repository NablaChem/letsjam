import sys, pathlib

sys.path.insert(0, str(pathlib.Path().resolve()))

from letsjam import TrafficWidget
from letsjam.maps import *
from letsjam.propagate import run_simulation


m = Capacity()


def car_drive(
    velocity: float,
    dist_to_next_car: float,
    dist_to_light: float,
    light_is_green: bool,
    is_truck: bool,
) -> float:
    return 10


def car_turn(
    exit_dirs: tuple[tuple[float, float], ...],
    first_car_dists: list[float],
    current_angle: float,
    exit_angles: list[float],
    sink_distances: list[float],
    is_slow_streets: list[bool],
    is_truck: bool,
) -> int:
    return 0


def traffic_light(
    inbound: list[list[tuple[float, float]]],
    outbound: list[list[tuple[float, float]]],
    last_switch: float,
    currently_green: int,
    frame: int,
) -> int:
    if frame < 10:
        return -1
    if inbound[0]:
        return 0
    return 1


traj = run_simulation(
    m, n_frames=240, car_drive=car_drive, car_turn=car_turn, traffic_light=traffic_light
)
