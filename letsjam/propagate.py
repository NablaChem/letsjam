from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass

from collections.abc import Callable

from .graph import Map
from .simulation import Trajectory, DISABLED

STOP_DISTANCE = 8

@dataclass
class Car:
    kind: int  # 0 = car, 1 = truck
    fuel: float
    velocity: float
    edge_id: int  # DISABLED (-1) = off map
    dist: float


def _build_graph(map_: Map) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """Return (inbound, outbound) edge index keyed by node id."""
    n_nodes = len(map_.nodes)
    inbound: dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    outbound: dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    for street_id, (from_node, to_node) in enumerate(map_.streets):
        outbound[from_node].append(street_id)
        inbound[to_node].append(street_id)
    return inbound, outbound


def _place_cars(map_: Map, inbound: dict[int, list[int]]) -> list[Car]:
    """Place cars on source streets, guaranteeing valid non-overlapping positions.

    Cars are distributed round-robin across all source streets.  For each
    source street the source node is moved further off-screen as needed so
    the street is long enough to hold its cars with:
      - 10 % extra total body length distributed as k random gaps
        (one leading gap per car, front-to-back), and
      - at least STOP_DISTANCE clearance between the frontmost car and
        the stop line, so a red light at frame 0 is always safe.

    The source node is never moved closer than its original position, so it
    can never appear on-screen.
    """
    source_streets = [
        s for s, (from_node, _) in enumerate(map_.streets) if not inbound[from_node]
    ]

    # All cars start disabled; only placed ones get an edge_id.
    cars: list[Car] = [
        Car(kind=map_.car_types[i], fuel=0.0, velocity=0.0, edge_id=DISABLED, dist=0.0)
        for i in range(map_.n_cars)
    ]

    if not source_streets:
        return cars

    # Round-robin assignment: car i → source_streets[i % n_sources]
    assigned: dict[int, list[int]] = {s: [] for s in source_streets}
    for i in range(map_.n_cars):
        assigned[source_streets[i % len(source_streets)]].append(i)

    for street_id, car_indices in assigned.items():
        if not car_indices:
            continue

        car_lens = [map_.car_visual_length(i) for i in car_indices]
        S = sum(car_lens)          # total body length on this street
        G = 0.1 * S                # total gap space (10 % extra)

        # Move source node so the street is long enough.
        # required_length ≥ cur_len  → source never moves on-screen.
        # required_length ≥ S*1.1 + 2*STOP_DISTANCE → stop_line lands at
        #   S*1.1 + STOP_DISTANCE, giving a full STOP_DISTANCE clearance
        #   between the frontmost car (placed at cursor = S*1.1) and the
        #   stop line before any movement happens.
        from_node, to_node = map_.streets[street_id]
        tx, ty = map_.nodes[to_node]
        sx, sy = map_.nodes[from_node]
        cur_len = math.hypot(tx - sx, ty - sy)
        if cur_len > 0:
            ux, uy = (sx - tx) / cur_len, (sy - ty) / cur_len
        else:
            ux, uy = -1.0, 0.0
        required_length = max(S * 1.1 + 2 * STOP_DISTANCE, cur_len)
        map_.nodes[from_node] = (tx + ux * required_length, ty + uy * required_length)

        # Sample k gaps, normalise to sum G.
        raw = [random.random() for _ in car_indices]
        scale = G / sum(raw)
        gaps = [r * scale for r in raw]

        # Place cars front-to-back: gap then car, gap then car, …
        # cursor starts at S*1.1, which is STOP_DISTANCE below the stop line.
        cursor = S * 1.1
        for car_idx, car_len, gap in zip(car_indices, car_lens, gaps):
            cursor -= gap
            cars[car_idx] = Car(
                kind=map_.car_types[car_idx],
                fuel=0.0,
                velocity=0.0,
                edge_id=street_id,
                dist=cursor,
            )
            cursor -= car_len

    return cars


def run_simulation(
    map_: Map,
    n_frames: int,
    car_drive: Callable,
    car_turn: Callable,
    traffic_light: Callable,
) -> Trajectory:
    """Run a full simulation and return the trajectory."""
    inbound, outbound = _build_graph(map_)
    cars = _place_cars(map_, inbound)
    n = map_.n_cars
    n_nodes = len(map_.nodes)

    light_green = [
        -1
    ] * n_nodes  # index into inbound[node] that is green (-1 = all red)
    light_last_switch = [0.0] * n_nodes  # frame of last switch

    traj = Trajectory(map_)

    for frame in range(n_frames):

        # ── Phase 1: update traffic lights ───────────────────────────────
        for node in range(n_nodes):
            ins = inbound[node]
            outs = outbound[node]

            if not ins:
                continue  # source node: no arriving traffic, light irrelevant

            inbound_data: list[list[tuple[float, float]]] = [
                sorted(
                    [
                        (
                            max(0.0, map_.street_length(s) - STOP_DISTANCE) - c.dist,
                            c.velocity,
                        )
                        for c in cars
                        if c.edge_id == s
                    ],
                    key=lambda x: x[0],
                )
                for s in ins
            ]
            outbound_data: list[list[tuple[float, float]]] = [
                sorted(
                    [(c.dist, c.velocity) for c in cars if c.edge_id == s],
                    key=lambda x: x[0],
                    reverse=True,
                )
                for s in outs
            ]

            new_green = traffic_light(
                inbound_data, outbound_data, light_last_switch[node], light_green[node]
            )

            if not (0 <= new_green < len(ins)):  # invalid: all red
                new_green = -1

            if new_green != light_green[node]:
                light_green[node] = new_green
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

            _, dest_node = map_.streets[street_id]
            street_length = map_.street_length(street_id)
            stop_line = max(0.0, street_length - STOP_DISTANCE)
            ins = inbound[dest_node]
            inbound_idx = ins.index(street_id)
            green_here = light_green[dest_node] == inbound_idx

            for rank, car_idx in enumerate(car_indices):
                c = cars[car_idx]

                bumper = math.inf
                if rank > 0:
                    ahead_idx = car_indices[rank - 1]
                    ahead = cars[ahead_idx]
                    if ahead.edge_id == street_id:  # still on same street
                        ahead_len = map_.car_visual_length(ahead_idx)
                        bumper = ahead.dist - ahead_len
                        dist_to_next = bumper - c.dist
                    else:  # car ahead just crossed: no obstruction on this street
                        dist_to_next = math.inf
                else:
                    dist_to_next = math.inf

                dist_to_light = math.inf if green_here else max(0.0, stop_line - c.dist)

                delta = car_drive(c.velocity, dist_to_next, dist_to_light, green_here)
                c.velocity = max(0.0, min(10.0, c.velocity + min(delta, 1)))
                new_dist = c.dist + c.velocity

                # rear-end prevention: keep gap >= length of car ahead
                if bumper < math.inf and new_dist >= bumper:
                    new_dist = bumper
                    c.velocity = ahead.velocity

                # handle end of edge
                if new_dist >= stop_line and not green_here:  # stop at stop line
                    c.dist = stop_line
                    c.velocity = 0.0
                    continue

                if new_dist >= street_length:
                    outs = outbound[dest_node]

                    if not outs:  # sink node: despawn
                        c.edge_id = DISABLED
                        c.dist = 0.0
                        c.velocity = 0.0
                        continue

                    # green: ask user where to turn
                    exit_dirs = tuple(map_.street_direction(s) for s in outs)
                    first_cars = [
                        min(
                            (cars[i].dist for i in range(n) if cars[i].edge_id == s),
                            default=math.inf,
                        )
                        for s in outs
                    ]
                    exit_idx = car_turn(exit_dirs, first_cars)

                    car_len = map_.car_visual_length(car_idx)

                    if not (0 <= exit_idx < len(outs)):  # invalid answer: block
                        c.dist = street_length - car_len
                        c.velocity = 0.0
                        continue

                    target = outs[exit_idx]
                    first_on = min(
                        (cars[i].dist for i in range(n) if cars[i].edge_id == target),
                        default=math.inf,
                    )

                    if first_on >= car_len:  # space available: turn
                        cur_dir = map_.street_direction(street_id)
                        dot = cur_dir[0] * exit_dirs[exit_idx][0] + cur_dir[1] * exit_dirs[exit_idx][1]
                        _angle = math.acos(max(-1.0, min(1.0, dot)))
                        c.velocity = c.velocity * max(0.1, 1.0 - _angle / math.pi)
                        c.edge_id = target
                        c.dist = max(0.0, new_dist - street_length)
                    else:  # target blocked: hold
                        c.dist = street_length - car_len
                        c.velocity = 0.0
                else:
                    c.dist = new_dist

        # ── Phase 3: record frame ─────────────────────────────────────────
        traj.append_dict(
            {
                i: (c.edge_id, c.dist)
                for i, c in enumerate(cars)
                if c.edge_id != DISABLED
            }
        )
        traj.append_lights(light_green)

    return traj
