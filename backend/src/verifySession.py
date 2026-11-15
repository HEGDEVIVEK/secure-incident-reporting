from fastapi import Request
from fastapi import HTTPException

import hashlib
from datetime import datetime, timezone
from src.mongodb import mongo_db

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in")

    # Login stored the hash as the session document's _id.
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = mongo_db.sessions.find_one({
        "_id": token_hash,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = mongo_db.users.find_one(
        {"_id": session["user_id"], "is_active": True},
        {"_id": 1, "role": 1, "username": 1},
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in")

    return user