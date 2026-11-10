"""Device whitelist, system-wide lockdown, failed-login tracking"""
import logging
import time

import db

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW_SECONDS = 600


class AccessDenied(Exception):
    """Deliberately vague: the screen never says why access was refused"""


def trigger_lockdown(reason, device_id=None):
    db.set_lockdown(reason, device_id)
    # The CloudWatch metric filter in monitoring.tf matches this exact token.
    logger.warning("LOCKDOWN_TRIGGERED reason=%s device=%s", reason, device_id)


def enforce_device_access(device_id):
    """Whitelist devices and Device ID check"""
    if db.lockdown_active():
        raise AccessDenied()
    if not db.device_is_whitelisted(device_id):
        trigger_lockdown("Unrecognised device", device_id)
        raise AccessDenied()


def report_failed_login(username):
    """Report failed logins"""
    if db.lockdown_active():
        return 0, True
    count = db.record_failed_login(username, int(time.time()), FAILED_LOGIN_WINDOW_SECONDS)
    if count >= MAX_FAILED_LOGINS:
        trigger_lockdown(f"{count} failed logins for one account", None)
        return count, True
    return count, False