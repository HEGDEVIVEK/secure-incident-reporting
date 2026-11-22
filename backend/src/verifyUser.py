from fastapi import HTTPException

from src import login_limiter
from src.mongodb import mongo_db
from src.security import password_hasher

DUMMY_HASH = password_hasher.hash("unused-placeholder")


def verify_credentials(username: str, password: str):
    # Reject locked usernames before doing any password work.
    wait = login_limiter.seconds_locked(username)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = mongo_db.users.find_one({"username": username})
    stored_hash = user["password_hash"] if user else DUMMY_HASH
    password_matches = password_hasher.verify(password, stored_hash)

    if not user or not password_matches or user.get("is_active") is not True:
        login_limiter.record_failure(username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    login_limiter.reset(username)
    return user