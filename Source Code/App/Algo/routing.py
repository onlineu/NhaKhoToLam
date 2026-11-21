"""Shortest delivery route (travelling salesman) from the warehouse, point 0, through every client stop."""
import math
import time
from itertools import permutations

MAX_BRUTE_STOPS = 9     # 9! = 362,880 routes
MAX_DP_STOPS = 12       # 2^12 * 12^2 steps


class RouteError(ValueError):
    pass


def haversine_matrix(points):
    """Straight-line distances in metres between (lat, lng) pairs."""
    def hav(a, b):
        p1, p2 = math.radians(a[0]), math.radians(b[0])
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
        return 2 * 6371008.8 * math.asin(math.sqrt(h))
    return [[hav(a, b) for b in points] for a in points]


def _cost(d, route, round_trip):
    total = sum(d[a][b] for a, b in zip(route, route[1:]))
    return total + (d[route[-1]][0] if round_trip else 0)


def brute_force(d, round_trip):
    """Exhaustive search: try every order of the stops. O(n!) time."""
    best, best_route, checked = math.inf, None, 0
    for perm in permutations(range(1, len(d))):
        route = (0,) + perm
        c = _cost(d, route, round_trip)
        checked += 1
        if c < best:
            best, best_route = c, route
    return list(best_route), best, checked


def held_karp(d, round_trip):
    """Dynamic programming over subsets of stops. O(n^2 * 2^n) time, O(n * 2^n) space."""
    m = len(d) - 1
    dp = {(1 << j, j): (d[0][j + 1], -1) for j in range(m)}   # (visited set, last stop) -> (cost, previous stop)
    for mask in range(1, 1 << m):
        for j in range(m):
            if (mask, j) not in dp:
                continue
            base = dp[(mask, j)][0]
            for k in range(m):
                if mask >> k & 1:
                    continue
                key, c = (mask | 1 << k, k), base + d[j + 1][k + 1]
                if key not in dp or c < dp[key][0]:
                    dp[key] = (c, j)
    full = (1 << m) - 1
    last = min(range(m), key=lambda j: dp[(full, j)][0] + (d[j + 1][0] if round_trip else 0))
    best = dp[(full, last)][0] + (d[last + 1][0] if round_trip else 0)
    route, mask = [], full
    while last != -1:
        route.append(last + 1)
        mask, last = mask & ~(1 << last), dp[(mask, last)][1]
    return [0] + route[::-1], best, len(dp)


def nearest_neighbour(d, round_trip):
    """Greedy: always drive to the closest unvisited stop. O(n^2) time, not always the shortest."""
    route, left, checked = [0], set(range(1, len(d))), 0
    while left:
        nxt = min(left, key=lambda j: d[route[-1]][j])
        checked += len(left)
        route.append(nxt)
        left.remove(nxt)
    return route, _cost(d, route, round_trip), checked


ALGORITHMS = {"brute_force": brute_force, "held_karp": held_karp, "nearest_neighbour": nearest_neighbour}


def solve(algorithm, d, round_trip=True):
    stops = len(d) - 1
    if algorithm == "brute_force" and stops > MAX_BRUTE_STOPS:
        raise RouteError(f"Brute force supports at most {MAX_BRUTE_STOPS} client stops. Pick another algorithm or remove stops.")
    if stops > MAX_DP_STOPS:
        raise RouteError(f"At most {MAX_DP_STOPS} client stops are supported.")
    start = time.perf_counter()
    order, distance, checked = ALGORITHMS[algorithm](d, round_trip)
    return {"algorithm": algorithm, "order": order, "distance_m": round(distance, 1), "checked": checked,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 3), "round_trip": round_trip}