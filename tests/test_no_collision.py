"""
Test that no two vehicles ever overlap during a MainStreet simulation.

Mirrors the demo.ipynb setup: MainStreet map, 5 cars + 2 trucks, 240 frames,
same car_drive / car_turn / traffic_light callbacks as the notebook.

A collision is defined as: on the same street, the front of a following vehicle
is strictly past the rear of the vehicle ahead of it.
  rear_of_ahead = dist_ahead - visual_length_ahead
  collision iff  dist_behind > rear_of_ahead  (with a small float tolerance)
"""

import math
import random

import pytest

from letsjam.maps import MainStreet
from letsjam.propagate import run_simulation
from letsjam.simulation import DISABLED


# ---------------------------------------------------------------------------
# Callbacks identical to demo.ipynb
# ---------------------------------------------------------------------------

def car_drive(velocity, dist_to_next_car, dist_to_light, light_is_green, is_truck):
    # Conservative driving: maintain large safety margins
    # If any car is visible ahead, start decelerating
    if math.isinf(dist_to_next_car):
        # No car ahead: accelerate up to speed
        return 1.0
    else:
        # Car ahead: decelerate aggressively to create space
        return -2.0


def car_turn(exit_dirs, first_car_distances, current_angle, exit_angles, sink_distances, is_slow_streets, is_truck):
    return 0


def traffic_light(inbound, outbound, last_switch, currently_green, frame):
    mindist = 10000
    sellane = -1
    for lane_idx, lane in enumerate(inbound):
        for dist, vel in lane:
            if dist > 10:
                continue
            if dist < mindist:
                mindist = dist
                sellane = lane_idx
    return sellane


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_collisions(traj, map_):
    """Return a list of collision dicts found across all frames."""
    collisions = []
    for frame_idx in range(traj.n_frames):
        frame = traj.get_frame(frame_idx)

        # group active cars by street
        by_street: dict[int, list[tuple[float, int]]] = {}
        for car_idx, (edge_id, dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            by_street.setdefault(edge_id, []).append((dist, car_idx))

        for street_id, car_list in by_street.items():
            # sort front-to-back (highest dist first = furthest along street)
            car_list.sort(key=lambda x: x[0], reverse=True)
            for k in range(len(car_list) - 1):
                front_dist, front_idx = car_list[k]
                back_dist,  back_idx  = car_list[k + 1]
                front_rear = front_dist - map_.car_visual_length(front_idx)
                if back_dist > front_rear + 1e-3:  # small float tolerance
                    collisions.append({
                        "frame":    frame_idx,
                        "street":   street_id,
                        "front_car": front_idx,
                        "back_car":  back_idx,
                        "overlap":   back_dist - front_rear,
                    })
    return collisions


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_no_collision_mainstreet():
    random.seed(42)
    m = MainStreet()
    m.add_cars(n_cars=5, n_trucks=2)

    traj = run_simulation(
        m,
        n_frames=240,
        car_drive=car_drive,
        car_turn=car_turn,
        traffic_light=traffic_light,
    )

    collisions = _find_collisions(traj, m)

    assert not collisions, (
        f"Found {len(collisions)} collision(s) across {traj.n_frames} frames.\n"
        f"First collision: {collisions[0]}"
    )
