"""VinDelivery backend entry point (AWS Lambda, Python).

Invoked directly by the EC2 tier with:
  {"action": "...", "device_id": "...", "user": {"username": "...", "groups": [...]}, "payload": {...}}
Always returns:
  {"ok": true,  "status": 200, "data": {...}}
  {"ok": false, "status": 4xx/5xx, "error": {"code": "...", "message": "..."}}
"""
import logging
import time

import benchmarking
import db
import routing
import security
import suggest
from sorting import binary_search_counted, quick_sort
from validation import (
    ValidationError,
    parse_device_id,
    parse_item_fields,
    parse_item_id,
    parse_quantity,
    parse_route,
    parse_search_terms,
    parse_username,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_GROUPS = {"staff", "admin"}
AUTO_ID_RETRIES = 10
MAX_NAME_RESULTS = 100
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def _ok(data, status=200):
    return {"ok": True, "status": status, "data": data}


def _err(status, code, message):
    return {"ok": False, "status": status, "error": {"code": code, "message": message}}


def _sorted_by_id(items):
    """Function 4: quick sort by item ID, timed with perf_counter."""
    start = time.perf_counter()
    result = quick_sort(items, key=lambda i: i["item_id"])
    return result, round((time.perf_counter() - start) * 1000, 3)


# ---------- actions ----------
def store_item(user, payload):
    manual_id, name, description, location = parse_item_fields(payload)
    quantity = parse_quantity(payload.get("quantity"))

    if manual_id is not None:
        try:
            item = db.put_item(manual_id, name, description, location, user["username"], quantity)
            suggest.invalidate()
        except db.DuplicateIdError:
            return _err(409, "DUPLICATE_ID", "That ID already exists.")
        return _ok({"item": item, "id_source": "manual"}, 201)

    # Automatic ID: a manually chosen ID may already occupy the counter's next value
    for _ in range(AUTO_ID_RETRIES):
        try:
            item = db.put_item(db.next_counter_id(), name, description, location, user["username"], quantity)
            suggest.invalidate()
            return _ok({"item": item, "id_source": "auto"}, 201)
        except db.DuplicateIdError:
            continue
    return _err(503, "ID_ASSIGNMENT_FAILED", "Could not assign an ID. Please try again.")


def find_item(user, payload):
    item_id = parse_item_id(payload.get("item_id"))
    item = db.get_item(item_id)
    if item is None:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"item": item})


def suggest_names(user, payload):
    return _ok({"suggestions": suggest.suggestions(parse_search_terms(payload.get("q")))})


def plan_route(user, payload):
    algorithm, points, round_trip, matrix = parse_route(payload)
    try:
        result = routing.solve(algorithm, matrix or routing.haversine_matrix(points), round_trip)
    except routing.RouteError as err:
        raise ValidationError("INVALID_INPUT", str(err))
    result["distance_source"] = "road" if matrix else "straight-line"
    return _ok(result)


def run_benchmark(user, payload):
    if "admin" not in user["groups"]:
        return _err(403, "FORBIDDEN", "Only managers can run the benchmark.")
    start = time.perf_counter()
    ids = db.scan_item_ids()
    read_ms = round((time.perf_counter() - start) * 1000, 3)
    if len(ids) < 2:
        return _err(400, "INVALID_INPUT", "Store at least 2 items before running the benchmark.")
    result = benchmarking.run(ids, db.get_item)
    result["read_ms"] = read_ms
    return _ok(result)


def find_item_binary(user, payload):
    """Option for staff: Quick Sort every item ID, then binary search the sorted list."""
    item_id = parse_item_id(payload.get("item_id"))
    ids = db.scan_item_ids()
    start = time.perf_counter()
    sorted_ids = quick_sort(ids)
    sort_ms = round((time.perf_counter() - start) * 1000, 3)
    start = time.perf_counter()
    index, steps = binary_search_counted(sorted_ids, item_id)
    search_ms = round((time.perf_counter() - start) * 1000, 3)
    item = db.get_item(item_id) if index >= 0 else None
    if item is None:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"item": item, "method": "binary_search", "total": len(sorted_ids), "position": index + 1,
                "steps": steps, "sort_ms": sort_ms, "search_ms": search_ms})


def search_name(user, payload):
    terms = parse_search_terms(payload.get("name"))
    items, sort_ms = _sorted_by_id(db.search_names(terms))
    if not items:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"count": len(items), "items": items[:MAX_NAME_RESULTS],
                "truncated": len(items) > MAX_NAME_RESULTS, "sort_ms": sort_ms})


def list_items(user, payload):
    try:
        page = max(1, int(payload.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(payload.get("page_size", DEFAULT_PAGE_SIZE))))
    except (TypeError, ValueError):
        raise ValidationError("INVALID_INPUT", "page and page_size must be whole numbers.")
    items, sort_ms = _sorted_by_id(db.scan_all())
    start = (page - 1) * page_size
    return _ok({
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "items": items[start:start + page_size],
        "sort_ms": sort_ms,
    })


def delete_item(user, payload):
    if "admin" not in user["groups"]:
        return _err(403, "FORBIDDEN", "Only managers can delete items.")
    item_id = parse_item_id(payload.get("item_id"))
    try:
        db.delete_item(item_id)
        suggest.invalidate()
    except db.ItemNotFoundError:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"deleted": item_id})


ACTIONS = {
    "store_item": store_item,
    "find_item": find_item,
    "find_item_binary": find_item_binary,
    "suggest_names": suggest_names,
    "plan_route": plan_route,
    "run_benchmark": run_benchmark,
    "search_name": search_name,
    "list_items": list_items,
    "delete_item": delete_item,
}


def _report_failed_login(event):
    username = parse_username(event.get("username"))
    count, locked = security.report_failed_login(username)
    if locked:
        return _err(423, "SYSTEM_LOCKED", "Access restricted. Contact an administrator.")
    return _ok({"failed_attempts": count})


def _read_user(event):
    user = event.get("user")
    if not isinstance(user, dict):
        raise ValidationError("INVALID_REQUEST", "Missing user.")
    username = parse_username(user.get("username"))
    groups = user.get("groups") or []
    if not isinstance(groups, list):
        raise ValidationError("INVALID_REQUEST", "Malformed groups.")
    return {"username": username, "groups": {g for g in groups if isinstance(g, str)}}


def lambda_handler(event, context):
    try:
        action = event.get("action")

        # Pre-login: the user has no token yet and no device check applies
        if action == "report_failed_login":
            return _report_failed_login(event)

        if action not in ACTIONS:
            return _err(400, "INVALID_REQUEST", "Unknown action.")

        device_id = parse_device_id(event.get("device_id"))
        user = _read_user(event)

        security.enforce_device_access(device_id)

        if not user["groups"] & ALLOWED_GROUPS:
            return _err(403, "FORBIDDEN", "Your account has no access to this system.")

        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValidationError("INVALID_REQUEST", "Malformed payload.")
        return ACTIONS[action](user, payload)

    except ValidationError as err:
        return _err(400, err.code, err.message)
    except security.AccessDenied:
        return _err(423, "SYSTEM_LOCKED", "Access restricted. Contact an administrator.")
    except Exception:
        logger.exception("Unhandled error")
        return _err(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")