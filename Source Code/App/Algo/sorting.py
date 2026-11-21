"""Sorting and searching for the VinDelivery backend (no external dependencies)."""


def _identity(x):
    return x


def quick_sort(data, key=_identity):
    """Return a new list sorted ascending by key(item).

    Iterative three-way quicksort with a median-of-three pivot:
      - three-way partitioning keeps runs of equal keys at O(n)
      - median-of-three avoids the O(n^2) worst case on already-sorted input
      - recursing into the smaller side and looping on the larger side keeps the
        explicit stack at O(log n), so there is no recursion-limit risk at 10,000+ items
    Average O(n log n).
    """
    a = list(data)
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            mid = (lo + hi) // 2
            x, y, z = key(a[lo]), key(a[mid]), key(a[hi])
            pivot = max(min(x, y), min(max(x, y), z))  # median of three

            lt, i, gt = lo, lo, hi
            while i <= gt:
                k = key(a[i])
                if k < pivot:
                    a[lt], a[i] = a[i], a[lt]
                    lt += 1
                    i += 1
                elif k > pivot:
                    a[i], a[gt] = a[gt], a[i]
                    gt -= 1
                else:
                    i += 1
            # a[lo:lt] < pivot, a[lt:gt+1] == pivot, a[gt+1:hi+1] > pivot
            if lt - lo < hi - gt:
                stack.append((gt + 1, hi))
                hi = lt - 1
            else:
                stack.append((lo, lt - 1))
                lo = gt + 1
    return a


def insertion_sort(data, key=_identity):
    """Baseline for benchmarking: O(n^2) average and worst case."""
    a = list(data)
    for i in range(1, len(a)):
        current = a[i]
        k = key(current)
        j = i - 1
        while j >= 0 and key(a[j]) > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = current
    return a


def binary_search(sorted_data, target, key=_identity):
    """Index of target in a list already sorted by key, or -1. O(log n)."""
    lo, hi = 0, len(sorted_data) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        k = key(sorted_data[mid])
        if k == target:
            return mid
        if k < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def binary_search_counted(sorted_data, target, key=_identity):
    """Same as binary_search, but returns (index, steps) so the UI can show how many halvings it took."""
    lo, hi, steps = 0, len(sorted_data) - 1, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        steps += 1
        k = key(sorted_data[mid])
        if k == target:
            return mid, steps
        if k < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1, steps


def merge_sort(data, key=_identity):
    """Stable bottom-up merge sort. O(n log n) in every case, O(n) extra space."""
    a, n = list(data), len(data)
    buf, width = a[:], 1
    while width < n:
        for lo in range(0, n, 2 * width):
            mid, hi = min(lo + width, n), min(lo + 2 * width, n)
            i, j, k = lo, mid, lo
            while i < mid and j < hi:
                if key(a[j]) < key(a[i]):
                    buf[k] = a[j]; j += 1
                else:
                    buf[k] = a[i]; i += 1
                k += 1
            buf[k:hi] = a[i:mid] + a[j:hi]
        a, buf = buf, a
        width *= 2
    return a


def heap_sort(data, key=_identity):
    """In-place heap sort on a copy. O(n log n) in every case, O(1) extra space."""
    a, n = list(data), len(data)

    def sift(root, end):
        while (child := 2 * root + 1) < end:
            if child + 1 < end and key(a[child]) < key(a[child + 1]):
                child += 1
            if key(a[root]) < key(a[child]):
                a[root], a[child] = a[child], a[root]
                root = child
            else:
                return

    for start in range(n // 2 - 1, -1, -1):
        sift(start, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        sift(0, end)
    return a


def linear_search(data, target):
    """Index of target, or -1. O(n)."""
    for i, v in enumerate(data):
        if v == target:
            return i
    return -1


def interpolation_search(sorted_data, target):
    """Guesses the position from the values. O(log log n) on evenly spread IDs, O(n) worst case."""
    lo, hi = 0, len(sorted_data) - 1
    while lo <= hi and sorted_data[lo] <= target <= sorted_data[hi]:
        if sorted_data[hi] == sorted_data[lo]:
            return lo if sorted_data[lo] == target else -1
        pos = lo + (target - sorted_data[lo]) * (hi - lo) // (sorted_data[hi] - sorted_data[lo])
        if sorted_data[pos] == target:
            return pos
        if sorted_data[pos] < target:
            lo = pos + 1
        else:
            hi = pos - 1
    return -1