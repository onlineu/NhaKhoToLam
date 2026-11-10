import logging
import time

import db
import security
from sorting import quick_sort
from validation import (
    ValidationError,
    parse_device_id,
    parse_item_fields,
    parse_item_id,
    parse_search_name,
    parse_username,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_GROUPS = {"staff", "admin"}
AUTO_ID_RETRIES = 10
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


# Actions
def store_item(user, payload):
    manual_id, name, description, location = parse_item_fields(payload)

    if manual_id is not None:
        try:
            item = db.put_item(manual_id, name, description, location, user["username"])
        except db.DuplicateIdError:
            return _err(409, "DUPLICATE_ID", "That ID already exists.")
        return _ok({"item": item, "id_source": "manual"}, 201)

    # Automatic ID: a manually chosen ID may already occupy the counter's next value
    for _ in range(AUTO_ID_RETRIES):
        try:
            item = db.put_item(db.next_counter_id(), name, description, location, user["username"])
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


def search_name(user, payload):
    name = parse_search_name(payload.get("name"))
    items, sort_ms = _sorted_by_id(db.query_by_name(name))
    if not items:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"count": len(items), "items": items, "sort_ms": sort_ms})


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
    except db.ItemNotFoundError:
        return _err(404, "ITEM_NOT_FOUND", "The item does not exist.")
    return _ok({"deleted": item_id})


ACTIONS = {
    "store_item": store_item,
    "find_item": find_item,
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