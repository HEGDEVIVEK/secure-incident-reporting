"""Brute-force protection for password checks (OWASP ASVS V2.2.1).

After MAX_FAILED_ATTEMPTS failed password checks for one username within
LOCKOUT_WINDOW, further attempts for that username get HTTP 429 until the
window passes. Only failures are counted, so many successful logins (for
example, the load tests) are never blocked.

Failures are stored in MongoDB (login_attempts collection) rather than in
memory, so the count is shared when uvicorn runs several worker processes.
The same rule applies whether or not the username exists, so the lockout
cannot be used to discover valid usernames.

Denied requests (401 and 429) are already logged by the request middleware
in api.py, so this module does not log anything itself.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from src.mongodb import mongo_db

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW = timedelta(minutes=15)


def ensure_not_locked(username: str):
    """Raise HTTP 429 if this username has too many recent failures."""
    since = datetime.now(timezone.utc) - LOCKOUT_WINDOW
    failures = mongo_db.login_attempts.count_documents(
        {"username": username, "created_at": {"$gt": since}}
    )
    if failures >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed sign-in attempts. Please wait 15 minutes and try again.",
        )


def record_failure(username: str):
    mongo_db.login_attempts.insert_one(
        {"username": username, "created_at": datetime.now(timezone.utc)}
    )


def clear_failures(username: str):
    mongo_db.login_attempts.delete_many({"username": username})
