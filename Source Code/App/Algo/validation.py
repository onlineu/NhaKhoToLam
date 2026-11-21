"""Input validation. Everything the EC2 tier sends is treated as untrusted."""
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


MAX_QUANTITY = 1_000_000
MAX_SEARCH_WORDS = 5


def parse_quantity(raw):
    """Whole number from 0 to 1,000,000. Missing or blank means 1."""
    bad = ValidationError("INVALID_INPUT", f"Quantity must be a whole number from 0 to {MAX_QUANTITY:,}.")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return 1
    if isinstance(raw, bool):
        raise bad
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and _PLAIN_ID.match(raw.strip()):
        value = int(raw.strip())
    else:
        raise bad
    if not 0 <= value <= MAX_QUANTITY:
        raise bad
    return value


def parse_search_terms(raw):
    """Search text to lowercase words: 'Life Jac' -> ['life', 'jac']. Any length from 1 character up."""
    words = _clean_text(raw, "Name", MAX_NAME, required=True).casefold().split()
    if len(words) > MAX_SEARCH_WORDS:
        raise ValidationError("INVALID_INPUT", f"Use at most {MAX_SEARCH_WORDS} words to search.")
    return words


def parse_route(payload):
    """Returns (algorithm, [(lat, lng), ...], round_trip, matrix_or_None). Point 0 is the warehouse."""
    bad = lambda msg: ValidationError("INVALID_INPUT", msg)
    algorithm = payload.get("algorithm")
    if algorithm not in ("brute_force", "held_karp", "nearest_neighbour"):
        raise bad("Choose a route algorithm.")
    raw = payload.get("points")
    if not isinstance(raw, list) or not 2 <= len(raw) <= 13:
        raise bad("Place the warehouse and between 1 and 12 client stops on the map.")
    points = []
    for p in raw:
        lat, lng = (p.get("lat"), p.get("lng")) if isinstance(p, dict) else (None, None)
        ok = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (lat, lng))
        if not ok or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise bad("A stop has an invalid position.")
        points.append((float(lat), float(lng)))
    matrix = payload.get("matrix")
    if matrix is not None:
        n = len(points)
        good = (isinstance(matrix, list) and len(matrix) == n and all(isinstance(r, list) and len(r) == n for r in matrix)
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < 1e9 for r in matrix for x in r))
        if not good:
            raise bad("The distance table is invalid.")
        matrix = [[float(x) for x in r] for r in matrix]
    return algorithm, points, bool(payload.get("round_trip", True)), matrix


def parse_device_id(raw):
    if not isinstance(raw, str) or not _DEVICE_ID.match(raw) or raw in _RESERVED_DEVICE_IDS:
        raise ValidationError("INVALID_REQUEST", "Missing or malformed device ID.")
    return raw


def parse_username(raw):
    if not isinstance(raw, str) or not _USERNAME.match(raw):
        raise ValidationError("INVALID_REQUEST", "Missing or malformed username.")
    return raw