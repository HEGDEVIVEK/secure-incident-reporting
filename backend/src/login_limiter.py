"""Brute-force protection for /login and /update-password.

Failed attempts are counted per username. After MAX_FAILURES failures within
WINDOW_SECONDS, that username is locked for LOCKOUT_SECONDS. A successful
login clears the counter.

State is kept in memory, so it resets when the server restarts and is not
shared between server processes (acceptable for a single instance).
"""
import threading
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 3 * 60
LOCKOUT_SECONDS = 3 * 60
MAX_TRACKED = 10_000  # caps memory use if someone tries many random usernames

_lock = threading.Lock()  # request handlers run in a thread pool
_failures: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def _key(username: str) -> str:
    return username.casefold()

def seconds_locked(username: str) -> int:
    key = _key(username)

    with _lock:
        now = time.monotonic()
        until = _locked_until.get(key)

        if until is not None:
            if until > now:
                return int(until - now) + 1

            del _locked_until[key]

        if len(_locked_until) >= MAX_TRACKED:
            # Remove expired entries before checking capacity.
            for name, expiry in list(_locked_until.items()):
                if expiry <= now:
                    del _locked_until[name]

            if len(_locked_until) >= MAX_TRACKED:
                # Temporarily throttle until the earliest lockout expires.
                return int(min(_locked_until.values()) - now) + 1

        return 0


def record_failure(username: str) -> None:
    key = _key(username)

    with _lock:
        now = time.monotonic()

        # Preserve an existing active lockout.
        if _locked_until.get(key, 0) > now:
            return

        _locked_until.pop(key, None)

        if len(_locked_until) >= MAX_TRACKED:
            for name, expiry in list(_locked_until.items()):
                if expiry <= now:
                    del _locked_until[name]

            if len(_locked_until) >= MAX_TRACKED:
                # An already-running request must not exceed capacity.
                return

        if key not in _failures and len(_failures) >= MAX_TRACKED:
            # Bound the number of partial failure counters.
            del _failures[next(iter(_failures))]

        recent = [
            timestamp
            for timestamp in _failures.get(key, [])
            if now - timestamp < WINDOW_SECONDS
        ]
        recent.append(now)

        if len(recent) >= MAX_FAILURES:
            _locked_until[key] = now + LOCKOUT_SECONDS
            _failures.pop(key, None)
        else:
            _failures[key] = recent


def reset(username: str) -> None:
    """Clear the counter after a successful login."""
    with _lock:
        _failures.pop(_key(username), None)