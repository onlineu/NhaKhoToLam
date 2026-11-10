# Sort and Search backend for VinDelivery - NhaKhoToLam


def _identity(x):
    return x

# Sorting Mech
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

# Searching Mech
def binary_search(sorted_data, target, key=_identity):
    """Search for target. O(log n)."""
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