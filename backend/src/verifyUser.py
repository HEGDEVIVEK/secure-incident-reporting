from fastapi import HTTPException
from src.security import password_hasher

from src.mongodb import mongo_db

DUMMY_HASH = password_hasher.hash("unused-placeholder")


def verify_credentials(username: str, password: str):
    user = mongo_db.users.find_one({"username": username})
    stored_hash = user["password_hash"] if user else DUMMY_HASH
    password_matches = password_hasher.verify(password, stored_hash)

    if not user or not password_matches or user.get("is_active") is not True:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return user