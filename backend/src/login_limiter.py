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
WINDOW_SECONDS = 1 * 60
LOCKOUT_SECONDS = 1 * 60
MAX_TRACKED = 10_000  # caps memory use if someone tries many random usernames

_lock = threading.Lock()  # request handlers run in a thread pool
_failures: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}


def _key(username: str) -> str:
    return username.casefold()


def seconds_locked(username: str) -> int:
    """Return the seconds left on a lockout, or 0 if the username is not locked."""
    key = _key(username)
    now = time.monotonic()
    with _lock:
        until = _locked_until.get(key)
        if until is None:
            return 0
        if until <= now:
            del _locked_until[key]
            return 0
        return int(until - now) + 1


def record_failure(username: str) -> None:
    """Count a failed attempt and lock the username once the limit is reached."""
    key = _key(username)
    now = time.monotonic()
    with _lock:
        if len(_locked_until) >= MAX_TRACKED:
            for name in [n for n, t in _locked_until.items() if t <= now]:
                del _locked_until[name]

        if key not in _failures and len(_failures) >= MAX_TRACKED:
            # Make room by dropping the oldest tracked username.
            del _failures[next(iter(_failures))]

        recent = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
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