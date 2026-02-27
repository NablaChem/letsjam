from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

from collections.abc import Callable

from .graph import Map
from .simulation import Trajectory, DISABLED


@dataclass
class Car:
    kind:     int    # 0 = car, 1 = truck
    fuel:     float
    velocity: float
    edge_id:  int    # DISABLED (-1) = off map
    dist:     float


def _build_graph(map_: Map) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """Return (inbound, outbound) edge index keyed by node id."""
    n_nodes = len(map_.nodes)
    inbound:  dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    outbound: dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    for street_id, (from_node, to_node) in enumerate(map_.streets):
        outbound[from_node].append(street_id)
        inbound[to_node].append(street_id)
    return inbound, outbound


def _place_cars(map_: Map, inbound: dict[int, list[int]]) -> list[Car]:
    """Randomly place cars on source streets (streets from nodes with no inbound)."""
    source_streets = [
        s for s, (from_node, _) in enumerate(map_.streets)
        if not inbound[from_node]
    ]
    cars: list[Car] = []
    for i in range(map_.n_cars):
        if source_streets:
            edge_id = random.choice(source_streets)
            dist    = random.uniform(0.0, map_.street_length(edge_id))
        else:
            edge_id = DISABLED
            dist    = 0.0
        cars.append(Car(kind=map_.car_types[i], fuel=0.0, velocity=0.0,
                        edge_id=edge_id, dist=dist))
    return cars


def run_simulation(
    map_: Map,
    n_frames: int,
    car_drive: Callable,
    car_turn: Callable,
    traffic_light: Callable,
    stop_distance: float | None = None,
) -> Trajectory:
    """Run a full simulation and return the trajectory.

    stop_distance: how far from the intersection centre cars stop at a red
                   light (default: map_.truck_length).
    """
    if stop_distance is None:
        stop_distance = map_.truck_length
    inbound, outbound = _build_graph(map_)
    cars    = _place_cars(map_, inbound)
    n       = map_.n_cars
    n_nodes = len(map_.nodes)

    light_green       = [-1]  * n_nodes  # index into inbound[node] that is green (-1 = all red)
    light_last_switch = [0.0] * n_nodes  # frame of last switch

    traj = Trajectory(map_)

    for frame in range(n_frames):

        # ── Phase 1: update traffic lights ───────────────────────────────
        for node in range(n_nodes):
            ins  = inbound[node]
            outs = outbound[node]

            if not ins:
                continue  # source node: no arriving traffic, light irrelevant

            inbound_data: list[list[tuple[float, float]]] = [
                sorted([(c.dist, c.velocity) for c in cars if c.edge_id == s],
                       key=lambda x: x[0], reverse=True)
                for s in ins
            ]
            outbound_data: list[list[tuple[float, float]]] = [
                sorted([(c.dist, c.velocity) for c in cars if c.edge_id == s],
                       key=lambda x: x[0], reverse=True)
                for s in outs
            ]

            new_green = traffic_light(inbound_data, outbound_data,
                                      light_last_switch[node])

            if not (0 <= new_green < len(ins)):  # invalid: all red
                new_green = -1

            if new_green != light_green[node]:
                light_green[node]       = new_green
                light_last_switch[node] = float(frame)

        # ── Phase 2: move cars ────────────────────────────────────────────
        # snapshot which cars are on each street at the start of this phase
        cars_by_street: dict[int, list[int]] = defaultdict(list)
        for i, c in enumerate(cars):
            if c.edge_id != DISABLED:
                cars_by_street[c.edge_id].append(i)

        for street_id, car_indices in cars_by_street.items():
            # process front-to-back (descending dist)
            car_indices.sort(key=lambda i: cars[i].dist, reverse=True)

            _, dest_node  = map_.streets[street_id]
            street_length = map_.street_length(street_id)
            stop_line     = max(0.0, street_length - stop_distance)
            ins           = inbound[dest_node]
            inbound_idx   = ins.index(street_id)
            green_here    = (light_green[dest_node] == inbound_idx)

            for rank, car_idx in enumerate(car_indices):
                c = cars[car_idx]

                bumper = math.inf
                if rank > 0:
                    ahead_idx = car_indices[rank - 1]
                    ahead     = cars[ahead_idx]
                    if ahead.edge_id == street_id:  # still on same street
                        ahead_len    = map_.car_visual_length(ahead_idx)
                        bumper       = ahead.dist - ahead_len
                        dist_to_next = bumper - c.dist
                    else:
                        dist_to_next = math.inf
                else:
                    dist_to_next = math.inf

                dist_to_light = max(0.0, stop_line - c.dist)

                delta      = car_drive(c.velocity, dist_to_next,
                                      dist_to_light, green_here)
                c.velocity = max(0.0, min(10.0, c.velocity + delta))
                new_dist   = c.dist + c.velocity

                # rear-end prevention: keep gap >= length of car ahead
                if bumper < math.inf and new_dist >= bumper:
                    new_dist   = bumper
                    c.velocity = ahead.velocity

                # handle end of edge
                if new_dist >= stop_line and not green_here:  # stop at stop line
                    c.dist     = stop_line
                    c.velocity = 0.0
                    continue

                if new_dist >= street_length:
                    outs = outbound[dest_node]

                    if not outs:                          # sink node: despawn
                        c.edge_id  = DISABLED
                        c.dist     = 0.0
                        c.velocity = 0.0
                        continue

                    # green: ask user where to turn
                    exit_dirs  = tuple(map_.street_direction(s) for s in outs)
                    first_cars = [
                        min((cars[i].dist for i in range(n) if cars[i].edge_id == s),
                            default=math.inf)
                        for s in outs
                    ]
                    exit_idx = car_turn(exit_dirs, first_cars)

                    if not (0 <= exit_idx < len(outs)):  # invalid answer: block
                        c.dist     = street_length
                        c.velocity = 0.0
                        continue

                    target   = outs[exit_idx]
                    car_len  = map_.car_visual_length(car_idx)
                    first_on = min(
                        (cars[i].dist for i in range(n) if cars[i].edge_id == target),
                        default=math.inf
                    )

                    if first_on >= car_len:              # space available: turn
                        c.edge_id = target
                        c.dist    = 0.0
                    else:                                # target blocked: hold
                        c.dist     = street_length
                        c.velocity = 0.0
                else:
                    c.dist = new_dist

        # ── Phase 3: record frame ─────────────────────────────────────────
        traj.append_dict({
            i: (c.edge_id, c.dist)
            for i, c in enumerate(cars)
            if c.edge_id != DISABLED
        })

    return traj
