"""Times the sorting and searching algorithms on the real item IDs read from DynamoDB."""
import random
import time

from sorting import binary_search, heap_sort, insertion_sort, interpolation_search, linear_search, merge_sort, quick_sort

INSERTION_MAX = 8000
SORTS = [
    ("Quick Sort (ours)", quick_sort, "O(n log n) average, O(n²) worst", 3),
    ("Merge Sort", merge_sort, "O(n log n) always", 3),
    ("Heap Sort", heap_sort, "O(n log n) always", 3),
    ("Insertion Sort", insertion_sort, "O(n²)", 1),
    ("Python sorted (Timsort)", sorted, "O(n log n), built in", 3),
]


def _best_ms(fn, repeats):
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return round(best * 1000, 3)


def _per_lookup_us(fn, targets):
    start = time.perf_counter()
    for t in targets:
        fn(t)
    return round((time.perf_counter() - start) / len(targets) * 1e6, 2)


def run(ids, get_item):
    n = len(ids)
    sorts = []
    for name, fn, complexity, repeats in SORTS:
        if fn is insertion_sort and n > INSERTION_MAX:
            sorts.append({"name": name, "ms": None, "complexity": complexity, "note": f"skipped above {INSERTION_MAX:,} items"})
        else:
            sorts.append({"name": name, "ms": _best_ms(lambda: fn(ids), repeats), "complexity": complexity, "note": ""})
    quick_ms = next(s["ms"] for s in sorts if s["name"].startswith("Quick"))

    ordered = quick_sort(ids)
    targets = random.sample(ordered, min(200, n))
    lookup = set(ids)
    set_build = _best_ms(lambda: set(ids), 3)

    searches = [
        {"name": "Binary search (ours)", "prep_ms": quick_ms, "per_lookup_us": _per_lookup_us(lambda t: binary_search(ordered, t), targets),
         "complexity": "O(log n) after sorting", "note": "needs the sort first"},
        {"name": "Interpolation search", "prep_ms": quick_ms, "per_lookup_us": _per_lookup_us(lambda t: interpolation_search(ordered, t), targets),
         "complexity": "O(log log n) if IDs are evenly spread", "note": "needs the sort first"},
        {"name": "Linear search", "prep_ms": 0, "per_lookup_us": _per_lookup_us(lambda t: linear_search(ids, t), targets),
         "complexity": "O(n)", "note": "no preparation"},
        {"name": "Hash set (Python set)", "prep_ms": set_build, "per_lookup_us": _per_lookup_us(lambda t: t in lookup, targets),
         "complexity": "O(1) average after building", "note": "built once per request"},
    ]
    db_targets = targets[:5]
    searches.append({"name": "DynamoDB direct lookup", "prep_ms": 0, "per_lookup_us": _per_lookup_us(get_item, db_targets),
                     "complexity": "O(1) key lookup, one network call", "note": "the real database, used by the app"})
    for s in searches:
        s["total_ms"] = round(s["prep_ms"] + s["per_lookup_us"] / 1000, 3)
    return {"n": n, "sorts": sorts, "searches": searches, "targets": len(targets)}