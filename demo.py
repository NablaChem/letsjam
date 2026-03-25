import sys, pathlib

sys.path.insert(0, str(pathlib.Path().resolve()))

from letsjam import TrafficWidget
from letsjam.maps import *
from letsjam.propagate import run_simulation


m = SmallTown()

# ── implement these ───────────────────────────────────────────────────────────
import random


def car_drive(
    velocity: float,
    dist_to_next_car: float,
    dist_to_light: float,
    light_is_green: bool,
    is_truck: bool,
) -> float:
    """Decide how much to accelerate or brake this tick.

    Called once per vehicle per frame.  Return a float:
      +1.0  → accelerate as fast as possible
       0.0  → keep current speed
      -1.0  → brake as hard as possible
    Any value in between is valid.  The engine clamps the result so that:
      - acceleration never exceeds 1.0 units/frame² (0.5 for trucks)
      - speed never exceeds 10 units/frame (8 for trucks, 4 on slow streets)
      - speed never goes below 0

    Args:
        velocity:        Current speed of this vehicle in world-units per frame.
        dist_to_next_car: Distance from the front bumper of this vehicle to the
                         rear bumper of the car directly ahead on the same street.
                         math.inf means the road ahead is clear.
        dist_to_light:   Distance from the front bumper to the stop line at the
                         end of this street.  math.inf means the light is green
                         (or there is no light), so you can ignore it.
        light_is_green:  True if the traffic light at the end of this street is
                         currently green.  When False you must stop before the
                         stop line (the engine enforces this, but your braking
                         logic makes it smooth).
        is_truck:        True if this vehicle is a truck.  Trucks are longer,
                         slower, and accelerate more slowly than cars.
    """
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
    """Choose which street to take at an intersection.

    Called once per vehicle when it reaches the end of its current street and
    needs to pick a direction.  Return the index (0, 1, 2, …) of the exit you
    want to take.  If you return an invalid index the vehicle will wait at the
    crossing and you will be asked again next frame.

    All list arguments are parallel: index 0 describes the first exit option,
    index 1 the second, and so on.  The number of options equals len(exit_dirs).

    Args:
        exit_dirs:       Unit vectors (dx, dy) pointing along each exit street.
                         Positive x is right, positive y is down (screen coords).
                         Example: (1.0, 0.0) means the street goes to the right.
        first_car_dists: For each exit, the distance from the start of that
                         street to the first car already on it.
                         math.inf means the exit street is empty.
                         Use this to avoid merging into a traffic jam.
        current_angle:   Compass bearing of the street you are leaving, in
                         degrees.  0 = North (up), 90 = East (right),
                         180 = South (down), 270 = West (left).
        exit_angles:     Compass bearing of each exit street, in the same
                         0–360 degree convention.  Compare with current_angle
                         to figure out which exits go straight, turn right, or
                         turn left.  For example, if current_angle is 90 and an
                         exit_angle is 180, that exit turns to the right (south).
        sink_distances:  Estimated total remaining distance (in world units) to
                         the nearest map exit if you take each option, computed
                         as the length of that exit street plus the shortest
                         path from its far end to the nearest sink.
                         math.inf means that exit leads to a dead end with no
                         path to any exit — avoid it!
                         Use this to route vehicles toward the shortest way out.
        is_slow_streets: True for each exit street that is a slow zone (max
                         speed 4).  Trucks and cars are automatically limited
                         there, but you might prefer to avoid slow streets when
                         in a hurry.
        is_truck:        True if this vehicle is a truck.  Trucks may prefer
                         wider or less congested routes.
    """
    return 0


def traffic_light(
    inbound: list[list[tuple[float, float]]],
    outbound: list[list[tuple[float, float]]],
    last_switch: float,
    currently_green: int,
    frame: int,
) -> int:
    """Decide which inbound lane gets a green light this frame.

    Called once per intersection per frame.  Return the index of the inbound
    lane that should be green.  Any value outside the valid range (0 to
    len(inbound)-1) means all lights are red.

    Args:
        inbound:         One list per inbound lane, each containing
                         (distance_to_stop_line, velocity) for every car
                         approaching the intersection on that lane, sorted
                         nearest-first.  distance_to_stop_line is 0.0 when a
                         car is right at the stop line, larger when it is
                         further away.  An empty list means no cars on that lane.
        outbound:        One list per outbound lane, each containing
                         (distance_from_start, velocity) for every car that
                         has already passed through the intersection, sorted
                         furthest-first.  Use this to detect congestion
                         downstream before letting more cars through.
        last_switch:     The frame number when the green light last changed.
                         Subtract from the current frame to find out how long
                         the current phase has been active.
                         Example: if frame=50 and last_switch=30, the current
                         phase has been active for 20 frames.
        currently_green: Index of the lane that is currently green, or -1 if
                         all lights are red.  Return the same index to keep the
                         current phase; return a different index to switch.
        frame:           The current simulation frame (starts at 0).  One frame
                         represents one unit of simulation time.  Use this for
                         simple time-based strategies, e.g. switch every 30
                         frames: return (frame // 30) % len(inbound).
    """
    return 7


# ── run & display ─────────────────────────────────────────────────────────────
traj = run_simulation(
    m, n_frames=240, car_drive=car_drive, car_turn=car_turn, traffic_light=traffic_light
)
TrafficWidget.from_simulation(m, traj)
