from __future__ import annotations

import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass

from collections.abc import Callable

from .maps.base import LevelMap
from .simulation import Trajectory, DISABLED

STOP_DISTANCE = 8
MIN_SPAWN_GAP = 2.0  # minimum bumper-to-bumper distance between spawned vehicles


@dataclass
class Car:
    kind: int  # 0 = car, 1 = truck
    fuel: float
    velocity: float
    edge_id: int  # DISABLED (-1) = off map
    dist: float


def _build_graph(map_: LevelMap) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    """Return (inbound, outbound) edge index keyed by node id."""
    n_nodes = len(map_.nodes)
    inbound: dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    outbound: dict[int, list[int]] = {i: [] for i in range(n_nodes)}
    for street_id, (from_node, to_node) in enumerate(map_.streets):
        outbound[from_node].append(street_id)
        inbound[to_node].append(street_id)
    return inbound, outbound


def _topo_street_order(
    n_nodes: int,
    streets: list[tuple[int, int]],
    inbound: dict[int, list[int]],
    outbound: dict[int, list[int]],
) -> list[int]:
    """Return street IDs ordered so downstream streets come first.

    Reverse BFS from sink nodes (out-degree 0), walking backwards via inbound
    edges.  Each node gets a rank equal to its BFS discovery order; streets are
    then sorted ascending by their destination node's rank.

    Nodes that are part of cycles are never dequeued and receive ranks after all
    DAG-reachable nodes, in arbitrary order.  Streets inside a pure cycle are
    therefore processed in an unspecified-but-consistent order; the downstream-
    first guarantee holds only for the acyclic portion of the graph.
    """
    out_deg = [len(outbound[i]) for i in range(n_nodes)]
    queue: deque[int] = deque(i for i in range(n_nodes) if out_deg[i] == 0)
    node_rank: dict[int, int] = {}
    while queue:
        node = queue.popleft()
        node_rank[node] = len(node_rank)
        for s in inbound[node]:
            pred = streets[s][0]
            out_deg[pred] -= 1
            if out_deg[pred] == 0:
                queue.append(pred)
    # cycle nodes: append in index order
    for node in range(n_nodes):
        if node not in node_rank:
            node_rank[node] = len(node_rank)
    return sorted(range(len(streets)), key=lambda s: node_rank[streets[s][1]])


def _place_cars(map_: LevelMap, inbound: dict[int, list[int]]) -> list[Car]:
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

    # Weighted allocation: each source gets cars proportional to its weight.
    weights = [max(0.0, map_.source_weights.get(s, 1.0)) for s in source_streets]
    total_w = sum(weights) or 1.0
    n_total = map_.n_cars
    exact = [w / total_w * n_total for w in weights]
    floors = [int(e) for e in exact]
    remainders = [e - f for e, f in zip(exact, floors)]
    deficit = n_total - sum(floors)
    for i in sorted(range(len(source_streets)), key=lambda i: -remainders[i])[:deficit]:
        floors[i] += 1

    # Shuffle car indices so types are interleaved, then slice per source.
    indices = list(range(map_.n_cars))
    random.shuffle(indices)
    assigned: dict[int, list[int]] = {}
    cursor_idx = 0
    for j, street_id in enumerate(source_streets):
        assigned[street_id] = indices[cursor_idx : cursor_idx + floors[j]]
        cursor_idx += floors[j]

    for street_id, car_indices in assigned.items():
        if not car_indices:
            continue

        car_lens = [map_.car_visual_length(i) for i in car_indices]
        S = sum(car_lens)  # total body length
        k = len(car_indices)
        # Each pair gets at least MIN_SPAWN_GAP; remainder is distributed randomly.
        G = max(0.1 * S, MIN_SPAWN_GAP * k)  # total gap space

        # Move source node so the street is long enough.
        from_node, to_node = map_.streets[street_id]
        tx, ty = map_.nodes[to_node]
        sx, sy = map_.nodes[from_node]
        cur_len = math.hypot(tx - sx, ty - sy)
        if cur_len > 0:
            ux, uy = (sx - tx) / cur_len, (sy - ty) / cur_len
        else:
            ux, uy = -1.0, 0.0
        required_length = max(S + G + 2 * STOP_DISTANCE, cur_len)
        map_.nodes[from_node] = (tx + ux * required_length, ty + uy * required_length)

        # Each gap = MIN_SPAWN_GAP + a random share of the extra budget.
        extra = G - MIN_SPAWN_GAP * k
        raw = [random.random() for _ in car_indices]
        raw_sum = sum(raw) or 1.0
        gaps = [MIN_SPAWN_GAP + r / raw_sum * extra for r in raw]

        # Place cars front-to-back: gap then car, gap then car, …
        # cursor starts at S+G, which is STOP_DISTANCE below the stop line.
        spawn_cursor = S + G
        for car_idx, car_len, gap in zip(car_indices, car_lens, gaps):
            spawn_cursor -= gap
            cars[car_idx] = Car(
                kind=map_.car_types[car_idx],
                fuel=0.0,
                velocity=0.0,
                edge_id=street_id,
                dist=spawn_cursor,
            )
            spawn_cursor -= car_len

    return cars


def run_simulation(
    map_: LevelMap,
    n_frames: int,
    car_drive: Callable,
    car_turn: Callable,
    traffic_light: Callable,
) -> Trajectory:
    """Run a full simulation and return the trajectory."""
    inbound, outbound = _build_graph(map_)
    n_nodes = len(map_.nodes)
    street_order = _topo_street_order(n_nodes, map_.streets, inbound, outbound)
    random.seed(map_.seed)
    cars = _place_cars(map_, inbound)
    n = map_.n_cars

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
        cars_by_street: dict[int, list[int]] = defaultdict(list)
        for i, c in enumerate(cars):
            if c.edge_id != DISABLED:
                cars_by_street[c.edge_id].append(i)

        transitioned: set[int] = set()

        for street_id in street_order:
            if street_id not in cars_by_street:
                continue
            car_indices = cars_by_street[street_id]
            # process front-to-back (descending dist)
            car_indices.sort(key=lambda i: cars[i].dist, reverse=True)

            _, dest_node = map_.streets[street_id]
            street_length = map_.street_length(street_id)
            stop_line = max(0.0, street_length - STOP_DISTANCE)
            ins = inbound[dest_node]
            inbound_idx = ins.index(street_id)
            green_here = light_green[dest_node] == inbound_idx

            for rank, car_idx in enumerate(car_indices):
                if car_idx in transitioned:
                    continue  # already moved this frame; kept in list for collision detection only
                c = cars[car_idx]
                cur_len = map_.car_visual_length(car_idx)

                bumper = math.inf
                if rank > 0:
                    ahead_idx = car_indices[rank - 1]
                    ahead = cars[ahead_idx]
                    if ahead.edge_id == street_id:  # still on same street
                        ahead_len = map_.car_visual_length(ahead_idx)
                        # dist is rendered as vehicle centre, so pack centre-to-centre
                        bumper = ahead.dist - ahead_len / 2 - cur_len / 2
                        dist_to_next = bumper - c.dist
                    else:  # car ahead just crossed: no obstruction on this street
                        dist_to_next = math.inf
                else:
                    dist_to_next = math.inf

                # distance from car front to stop line (front = centre + half-length)
                dist_to_light = (
                    math.inf
                    if green_here
                    else max(0.0, stop_line - cur_len / 2 - c.dist)
                )

                delta = car_drive(c.velocity, dist_to_next, dist_to_light, green_here)
                max_speed = 8.0 if c.kind == 1 else 10.0
                max_accel = 0.5 if c.kind == 1 else 1.0
                c.velocity = max(
                    0.0, min(max_speed, c.velocity + min(delta, max_accel))
                )
                new_dist = c.dist + c.velocity

                # rear-end prevention: keep centres at least (half_ahead + half_cur) apart
                if bumper < math.inf and new_dist >= bumper:
                    new_dist = bumper
                    c.velocity = ahead.velocity

                # handle end of edge: stop when front reaches stop line
                if new_dist + cur_len / 2 >= stop_line and not green_here:
                    c.dist = max(
                        0.0, stop_line - cur_len / 2
                    )  # centre stops so front == stop_line
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

                    # For each outbound street, find the first (minimum-dist) car
                    # and remember its index so we can check its length and velocity.
                    first_cars_info: list[tuple[float, int]] = []
                    for s in outs:
                        cands = [
                            (cars[i].dist, i)
                            for i in cars_by_street[s]
                            if i not in transitioned
                        ]
                        first_cars_info.append(min(cands, default=(math.inf, -1)))

                    exit_idx = car_turn(exit_dirs, [d for d, _ in first_cars_info])

                    car_len = map_.car_visual_length(car_idx)

                    if not (0 <= exit_idx < len(outs)):  # invalid answer: block
                        c.dist = street_length - car_len
                        c.velocity = 0.0
                        continue

                    first_on, first_on_idx = first_cars_info[exit_idx]
                    blocker_len = (
                        map_.car_visual_length(first_on_idx) if first_on_idx != -1 else 0.0
                    )
                    blocker_vel = cars[first_on_idx].velocity if first_on_idx != -1 else 0.0

                    entry_dist = max(0.0, new_dist - street_length)
                    safe_entry = first_on - blocker_len / 2 - cur_len / 2
                    if safe_entry >= 0:  # blocker has cleared the entry point: cross
                        target = outs[exit_idx]
                        cur_dir = map_.street_direction(street_id)
                        dot = (
                            cur_dir[0] * exit_dirs[exit_idx][0]
                            + cur_dir[1] * exit_dirs[exit_idx][1]
                        )
                        _angle = math.acos(max(-1.0, min(1.0, dot)))
                        c.velocity = c.velocity * max(0.1, 1.0 - _angle / math.pi)
                        if entry_dist > safe_entry:  # would overlap: clamp like rear-end
                            c.dist = safe_entry
                            c.velocity = min(c.velocity, blocker_vel)
                        else:
                            c.dist = entry_dist
                        c.edge_id = target
                        transitioned.add(car_idx)
                    else:  # blocker still at entry: hold at end of source street
                        c.dist = street_length - cur_len / 2
                        c.velocity = blocker_vel
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

        if all(c.edge_id == DISABLED for c in cars):
            print(f"All cars cleared in {frame} minutes.")
            break
    else:
        print("Did not finish")

    return traj
