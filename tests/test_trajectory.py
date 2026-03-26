"""
Parametrized trajectory test suite for run_simulation.

Tests the trajectory validation across multiple maps with simple decision functions.
Each test validates that:
  1. No cars overlap (considering their visual lengths)
  2. No car moves backwards on a single road
  3. Edge IDs and positions are consistent
"""

import math
import random

import pytest

from letsjam.maps import (
    BabySteps,
    Capacity,
    Detour,
    Highway,
    LessIsMore,
    MainStreet,
    NoEscape,
    SmallTown,
)
from letsjam.propagate import run_simulation
from letsjam.simulation import DISABLED


# ---------------------------------------------------------------------------
# Simple decision functions for testing
# ---------------------------------------------------------------------------


def simple_car_drive(velocity, dist_to_next_car, dist_to_light, light_is_green, is_truck):
    """Always accelerate."""
    return 1.0


def car_turn_first_exit(exit_dirs, first_car_distances, current_angle, exit_angles, sink_distances, is_slow_streets, is_truck):
    """Always take the first exit."""
    return 0


def traffic_light_first_entry(inbound, outbound, last_switch, currently_green, frame):
    """Always put green on the first entry."""
    return 0


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------


def _find_collisions(traj, map_):
    """Return a list of collision dicts found across all frames.

    A collision is defined as: on the same street, the front of a following vehicle
    is strictly past the rear of the vehicle ahead of it.
    """
    collisions = []
    for frame_idx in range(traj.n_frames):
        frame = traj.get_frame(frame_idx)

        # group active cars by street
        by_street = {}
        for car_idx, (edge_id, dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            by_street.setdefault(edge_id, []).append((dist, car_idx))

        for street_id, car_list in by_street.items():
            # sort front-to-back (highest dist first = furthest along street)
            car_list.sort(key=lambda x: x[0], reverse=True)
            for k in range(len(car_list) - 1):
                front_dist, front_idx = car_list[k]
                back_dist, back_idx = car_list[k + 1]
                # dist is vehicle center, so rear = center - length/2
                front_len = map_.car_visual_length(front_idx)
                back_len = map_.car_visual_length(back_idx)
                front_rear = front_dist - front_len / 2
                back_front = back_dist + back_len / 2
                if back_front > front_rear + 0.1:  # small tolerance for floating point
                    collisions.append({
                        "frame": frame_idx,
                        "street": street_id,
                        "front_car": front_idx,
                        "back_car": back_idx,
                        "overlap": back_front - front_rear,
                    })
    return collisions


# ---------------------------------------------------------------------------
# Backward movement detection
# ---------------------------------------------------------------------------


def _find_backward_movement(traj, map_):
    """Return a list of frames where a car moved backwards on a street.

    Backward movement is defined as: dist[frame+1] < dist[frame] while on the same street.
    """
    backward_moves = []
    for frame_idx in range(traj.n_frames - 1):
        frame = traj.get_frame(frame_idx)
        next_frame = traj.get_frame(frame_idx + 1)

        for car_idx, (edge_id, dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            next_edge_id, next_dist = next_frame[car_idx]
            # Same street, but moved backwards
            if next_edge_id == edge_id and next_dist < dist - 0.5:
                backward_moves.append({
                    "frame": frame_idx,
                    "car": car_idx,
                    "street": edge_id,
                    "dist_before": dist,
                    "dist_after": next_dist,
                    "delta": next_dist - dist,
                })
    return backward_moves


# ---------------------------------------------------------------------------
# Invalid position detection
# ---------------------------------------------------------------------------


def _find_invalid_positions(traj, map_):
    """Return a list of invalid positions.

    A position is invalid if:
      - edge_id is not -1 and not in map_.streets
      - dist is negative
      - dist exceeds street length
    """
    invalid = []
    for frame_idx in range(traj.n_frames):
        frame = traj.get_frame(frame_idx)
        for car_idx, (edge_id, dist) in enumerate(frame):
            if edge_id == DISABLED:
                continue
            # Edge ID must be valid
            if not (0 <= edge_id < len(map_.streets)):
                invalid.append({
                    "frame": frame_idx,
                    "car": car_idx,
                    "issue": "invalid_edge_id",
                    "edge_id": edge_id,
                })
                continue
            # Distance must be non-negative
            if dist < -0.01:
                invalid.append({
                    "frame": frame_idx,
                    "car": car_idx,
                    "issue": "negative_distance",
                    "dist": dist,
                    "street": edge_id,
                })
                continue
            # Distance must not exceed street length
            street_len = map_.street_length(edge_id)
            if dist > street_len + 0.1:
                invalid.append({
                    "frame": frame_idx,
                    "car": car_idx,
                    "issue": "distance_exceeds_street",
                    "dist": dist,
                    "street_length": street_len,
                    "street": edge_id,
                })
    return invalid


# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------


@pytest.fixture(params=[
    ("BabySteps", BabySteps()),
    ("Capacity", Capacity()),
    ("Detour", Detour()),
    ("Highway", Highway()),
    ("LessIsMore", LessIsMore()),
    ("MainStreet", MainStreet()),
    ("NoEscape", NoEscape()),
    ("SmallTown", SmallTown()),
], ids=lambda x: x[0])
def map_fixture(request):
    """Fixture providing each test map."""
    name, map_ = request.param
    # Add cars to each map if not already added
    if map_.n_cars == 0:
        map_.add_cars(n_cars=5, n_trucks=2)
    return name, map_


# ---------------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------------


class TestTrajectoryValid:
    """Test that trajectories satisfy basic validity constraints."""

    def test_no_collisions(self, map_fixture):
        """No cars should overlap at any frame."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=100,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        collisions = _find_collisions(traj, map_)
        assert not collisions, (
            f"[{name}] Found {len(collisions)} collision(s).\n"
            f"First: {collisions[0]}"
        )


    def test_no_backward_movement(self, map_fixture):
        """No car should move backwards on a single street."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=100,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        backward = _find_backward_movement(traj, map_)
        assert not backward, (
            f"[{name}] Found {len(backward)} backward movement(s).\n"
            f"First: {backward[0]}"
        )

    def test_valid_positions(self, map_fixture):
        """All car positions should be valid (correct edge_id, non-negative dist)."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=100,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        invalid = _find_invalid_positions(traj, map_)
        assert not invalid, (
            f"[{name}] Found {len(invalid)} invalid position(s).\n"
            f"First: {invalid[0]}"
        )




class TestTrajectoryProperties:
    """Test general trajectory properties."""

    def test_trajectory_frames_positive(self, map_fixture):
        """Trajectory should have positive number of frames."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=50,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        assert traj.n_frames > 0, f"[{name}] Trajectory has no frames."

    def test_trajectory_car_count_matches(self, map_fixture):
        """Trajectory car count should match map car count."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=50,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        assert traj.n_cars == map_.n_cars, (
            f"[{name}] Car count mismatch: {traj.n_cars} vs {map_.n_cars}"
        )

    def test_all_cars_eventually_clear(self, map_fixture):
        """All cars should eventually clear (become DISABLED) or stay on-map."""
        name, map_ = map_fixture
        random.seed(42)

        traj = run_simulation(
            map_,
            n_frames=200,  # generous frame count
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        # In the final frame, check that we don't have impossible states
        final_frame = traj.get_frame(traj.n_frames - 1)
        for car_idx, (edge_id, dist) in enumerate(final_frame):
            # Must be either disabled or on a valid street
            assert edge_id == DISABLED or (0 <= edge_id < len(map_.streets)), (
                f"[{name}] Car {car_idx} has invalid edge_id {edge_id} in final frame."
            )


class TestLongRunSimulation:
    """Test longer simulations to ensure stability."""

    def test_extended_simulation(self):
        """A longer simulation on SmallTown should remain valid."""
        random.seed(42)
        map_ = SmallTown()
        map_.add_cars(n_cars=10, n_trucks=3)

        traj = run_simulation(
            map_,
            n_frames=300,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        collisions = _find_collisions(traj, map_)
        backward = _find_backward_movement(traj, map_)
        invalid = _find_invalid_positions(traj, map_)

        assert not collisions, f"Extended sim: {len(collisions)} collisions"
        assert not backward, f"Extended sim: {len(backward)} backward moves"
        assert not invalid, f"Extended sim: {len(invalid)} invalid positions"


class TestHighwayCapacity:
    """Test highway-specific scenarios."""

    def test_highway_multi_lane(self):
        """Highway with multiple lanes should handle cars without collisions."""
        random.seed(42)
        map_ = Highway()
        map_.add_cars(n_cars=15, n_trucks=5)

        traj = run_simulation(
            map_,
            n_frames=150,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        collisions = _find_collisions(traj, map_)
        assert not collisions, f"Highway collision: {collisions[0] if collisions else 'none'}"


class TestTrafficLights:
    """Test simulations with traffic light constraints."""

    def test_mainstreet_with_lights(self):
        """MainStreet with traffic lights should be navigable."""
        random.seed(42)
        map_ = MainStreet()
        map_.add_cars(n_cars=8, n_trucks=2)

        traj = run_simulation(
            map_,
            n_frames=200,
            car_drive=simple_car_drive,
            car_turn=car_turn_first_exit,
            traffic_light=traffic_light_first_entry,
        )

        collisions = _find_collisions(traj, map_)
        assert not collisions, f"MainStreet collision: {len(collisions)}"
