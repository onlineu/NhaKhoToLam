"""Deal with DynamoDB"""
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

_cache = {}


class DuplicateIdError(Exception):
    pass


class ItemNotFoundError(Exception):
    pass


def reset_cache():
    """Used by tests so each test builds fresh clients"""
    _cache.clear()


def table(env_var):
    if "ddb" not in _cache:
        _cache["ddb"] = boto3.resource("dynamodb")
    if env_var not in _cache:
        _cache[env_var] = _cache["ddb"].Table(os.environ[env_var])
    return _cache[env_var]


def _plain(value):
    """DynamoDB returns numbers as Decimal, convert so results are JSON serialisable."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _is_condition_failure(err):
    return err.response["Error"]["Code"] == "ConditionalCheckFailedException"


# items
def next_counter_id():
    resp = table("COUNTERS_TABLE").update_item(
        Key={"counter_name": "item_id"},
        UpdateExpression="ADD current_value :inc",
        ExpressionAttributeValues={":inc": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["current_value"])


def put_item(item_id, name, description, location, created_by):
    item = {
        "item_id": item_id,
        "name": name,
        "name_lower": name.casefold(),
        "description": description,
        "location": location,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        table("ITEMS_TABLE").put_item(
            Item=item, ConditionExpression="attribute_not_exists(item_id)"
        )
    except ClientError as err:
        if _is_condition_failure(err):
            raise DuplicateIdError(item_id) from err
        raise
    return _plain(item)


def get_item(item_id):
    resp = table("ITEMS_TABLE").get_item(Key={"item_id": item_id}, ConsistentRead=True)
    item = resp.get("Item")
    return _plain(item) if item else None


def query_by_name(name):
    """All items whose name matches case-insensitively"""
    kwargs = {
        "IndexName": "name-index",
        "KeyConditionExpression": Key("name_lower").eq(name.casefold()),
    }
    items = []
    while True:
        resp = table("ITEMS_TABLE").query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return [_plain(i) for i in items]
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def scan_all():
    kwargs = {}
    items = []
    while True:
        resp = table("ITEMS_TABLE").scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return [_plain(i) for i in items]
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def delete_item(item_id):
    try:
        table("ITEMS_TABLE").delete_item(
            Key={"item_id": item_id}, ConditionExpression="attribute_exists(item_id)"
        )
    except ClientError as err:
        if _is_condition_failure(err):
            raise ItemNotFoundError(item_id) from err
        raise


# Whitelist and Lockdown
def lockdown_active():
    resp = table("WHITELIST_TABLE").get_item(Key={"device_id": "LOCKDOWN"}, ConsistentRead=True)
    return bool(resp.get("Item", {}).get("active", False))


def device_is_whitelisted(device_id):
    resp = table("WHITELIST_TABLE").get_item(Key={"device_id": device_id}, ConsistentRead=True)
    return "Item" in resp


def set_lockdown(reason, device_id=None):
    table("WHITELIST_TABLE").update_item(
        Key={"device_id": "LOCKDOWN"},
        UpdateExpression="SET #a = :t, reason = :r, triggered_at = :ts, trigger_device = :d",
        ExpressionAttributeNames={"#a": "active"},
        ExpressionAttributeValues={
            ":t": True,
            ":r": reason,
            ":ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ":d": device_id or "n/a",
        },
    )


def record_failed_login(username, now, window_seconds):
    """Atomically count failures inside a rolling window. Returns the current count."""
    key = {"device_id": f"FAILED#{username}"}
    tbl = table("WHITELIST_TABLE")
    try:
        resp = tbl.update_item(
            Key=key,
            UpdateExpression="SET attempts = attempts + :one, last_ts = :now",
            ConditionExpression="attribute_exists(device_id) AND last_ts > :cutoff",
            ExpressionAttributeValues={":one": 1, ":now": now, ":cutoff": now - window_seconds},
            ReturnValues="ALL_NEW",
        )
    except ClientError as err:
        if not _is_condition_failure(err):
            raise
        # no row yet, or the last failure was outside the window: start counting again
        resp = tbl.update_item(
            Key=key,
            UpdateExpression="SET attempts = :one, last_ts = :now",
            ExpressionAttributeValues={":one": 1, ":now": now},
            ReturnValues="ALL_NEW",
        )
    return int(resp["Attributes"]["attempts"])