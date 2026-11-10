"""Input validation."""
import re

MAX_ID = 10**12
MAX_NAME = 100
MAX_DESCRIPTION = 500
MAX_LOCATION = 50

_PLAIN_ID = re.compile(r"^[0-9]+$")
_GROUPED_ID = re.compile(r"^[0-9]{1,3}(,[0-9]{3})+$")  # 9,030 ok; 67,6767 not
_DEVICE_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_USERNAME = re.compile(r"^[A-Za-z0-9_.@+-]{1,128}$")
_RESERVED_DEVICE_IDS = {"LOCKDOWN"}


class ValidationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_item_id(raw):
    """Accepts 9030, "9030" or "9,030". Rejects "ASD2343", "67,6767", 0, negatives, floats."""
    bad = ValidationError(
        "INVALID_ID",
        "The ID is invalid. Use digits only, for example 9030 or 9,030.",
    )
    if isinstance(raw, bool):
        raise bad
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not (_PLAIN_ID.match(s) or _GROUPED_ID.match(s)):
            raise bad
        value = int(s.replace(",", ""))
    else:
        raise bad
    if not 1 <= value <= MAX_ID:
        raise bad
    return value


def _clean_text(value, field, max_len, required, allow_newlines=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError("INVALID_INPUT", f"{field} must be text.")
    value = value.strip() if allow_newlines else " ".join(value.split())
    if required and not value:
        raise ValidationError("INVALID_INPUT", f"{field} is required.")
    if len(value) > max_len:
        raise ValidationError("INVALID_INPUT", f"{field} must be at most {max_len} characters.")
    for ch in value:
        if not ch.isprintable() and not (allow_newlines and ch == "\n"):
            raise ValidationError("INVALID_INPUT", f"{field} contains invalid characters.")
    return value


def parse_item_fields(payload):
    """Validate a store request. Returns (item_id_or_None, name, description, location)."""
    name = _clean_text(payload.get("name"), "Name", MAX_NAME, required=True)
    description = _clean_text(payload.get("description"), "Description", MAX_DESCRIPTION,
                              required=False, allow_newlines=True)
    location = _clean_text(payload.get("location"), "Shelf/aisle", MAX_LOCATION, required=True)

    raw_id = payload.get("item_id")
    item_id = None
    if raw_id is not None and not (isinstance(raw_id, str) and raw_id.strip() == ""):
        item_id = parse_item_id(raw_id)
    return item_id, name, description, location


def parse_search_name(raw):
    return _clean_text(raw, "Name", MAX_NAME, required=True)


def parse_device_id(raw):
    if not isinstance(raw, str) or not _DEVICE_ID.match(raw) or raw in _RESERVED_DEVICE_IDS:
        raise ValidationError("INVALID_REQUEST", "Missing or malformed device ID.")
    return raw


def parse_username(raw):
    if not isinstance(raw, str) or not _USERNAME.match(raw):
        raise ValidationError("INVALID_REQUEST", "Missing or malformed username.")
    return raw