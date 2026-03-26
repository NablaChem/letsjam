"""
Test that distance between consecutive cars at a traffic light never increases.

Scenario: A traffic light alternates between lanes, initially blocking both lanes
(frames 0-9), then allowing cars through. Some cars may stop even when green.
The distance between two consecutive cars approaching the light should never
increase after frame 10 (when blocking ends).
"""

import random

import pytest

from letsjam.maps import Capacity
from letsjam.propagate import run_simulation
from letsjam.simulation import DISABLED

# car_types: 0 = car, 1 = truck


# ---------------------------------------------------------------------------
# Callbacks from demo.py
# ---------------------------------------------------------------------------

def car_drive(velocity, dist_to_next_car, dist_to_light, light_is_green, is_truck):
    """Constant velocity (from demo.py)."""
    return 10


def car_turn(exit_dirs, first_car_distances, current_angle, exit_angles, sink_distances, is_slow_streets, is_truck):
    """Always take first exit (from demo.py)."""
    return 0


def traffic_light(inbound, outbound, last_switch, currently_green, frame):
    """
    Allow lane 0 to pass, then alternate.
    Frames 0-9: block both lanes (return -1).
    After frame 10: return 0 if lane 0 has cars, else 1.
    """
    if frame < 10:
        return -1
    if inbound[0]:
        return 0
    return 1


# ---------------------------------------------------------------------------
# Test helper: track distance between consecutive cars
# ---------------------------------------------------------------------------

def test_traffic_light_no_increasing_spacing():
    """
    Distance between two consecutive cars approaching a traffic light
    should never increase from frame 10 onward (until light switches).
    """
    random.seed(42)
    m = Capacity()
    m.add_cars(n_cars=5, n_trucks=2)

    traj = run_simulation(
        m,
        n_frames=240,
        car_drive=car_drive,
        car_turn=car_turn,
        traffic_light=traffic_light,
    )

    # Track spacing violations
    violations = []

    # Pre-compute which cars are on which street for each frame
    street_sets: list[dict[int, set[int]]] = []
    for frame_idx in range(traj.n_frames):
        frame = traj.get_frame(frame_idx)
        by_street: dict[int, set[int]] = {}
        for car_idx, (edge_id, _dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            by_street.setdefault(edge_id, set()).add(car_idx)
        street_sets.append(by_street)

    # Start from frame 10 onwards
    for frame_idx in range(10, traj.n_frames - 1):
        frame = traj.get_frame(frame_idx)
        next_frame = traj.get_frame(frame_idx + 1)

        # Group cars by street
        by_street = {}
        next_by_street = {}

        for car_idx, (edge_id, dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            by_street.setdefault(edge_id, []).append((dist, car_idx))

        for car_idx, (edge_id, dist) in enumerate(next_frame):
            if edge_id == DISABLED:
                continue
            next_by_street.setdefault(edge_id, []).append((dist, car_idx))

        prev_street_sets = street_sets[frame_idx - 1]

        # For each street, check consecutive cars
        for street_id, car_list in by_street.items():
            if street_id not in next_by_street:
                continue

            # Sort front-to-back
            car_list.sort(key=lambda x: x[0], reverse=True)
            next_car_list = next_by_street[street_id]
            next_car_list.sort(key=lambda x: x[0], reverse=True)

            # Check each pair of consecutive cars
            for k in range(len(car_list) - 1):
                front_dist, front_idx = car_list[k]
                back_dist, back_idx = car_list[k + 1]

                # Find same cars in next frame
                next_front = None
                next_back = None
                for d, idx in next_car_list:
                    if idx == front_idx:
                        next_front = d
                    if idx == back_idx:
                        next_back = d

                if next_front is None or next_back is None:
                    # Car left the street, skip
                    continue

                # Skip mixed-type pairs (cars and trucks have different
                # max speed / acceleration, so cars naturally pull away)
                if m.car_types[front_idx] != m.car_types[back_idx]:
                    continue

                # Skip if either car just arrived on this street this frame
                # (they weren't here in the previous frame, so their velocity
                # relative to cars already on the street is arbitrary)
                prev_on_street = prev_street_sets.get(street_id, set())
                if front_idx not in prev_on_street or back_idx not in prev_on_street:
                    continue

                # Calculate spacing (distance between fronts)
                spacing_now = front_dist - back_dist
                spacing_next = next_front - next_back

                # Spacing should not increase (allow small tolerance for floating point)
                if spacing_next > spacing_now + 1e-3:
                    violations.append({
                        "frame": frame_idx,
                        "street": street_id,
                        "front_car": front_idx,
                        "back_car": back_idx,
                        "spacing_now": spacing_now,
                        "spacing_next": spacing_next,
                        "increase": spacing_next - spacing_now,
                    })

    assert not violations, (
        f"Found {len(violations)} spacing violation(s).\n"
        f"First violation: {violations[0]}"
    )
