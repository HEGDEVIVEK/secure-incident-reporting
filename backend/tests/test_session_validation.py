import hashlib
import secrets
from datetime import timedelta, timezone
from getpass import getpass
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import app
from src.mongodb import mongo_db

username = input("Active test account username: ").strip()
password = getpass("Password: ")

with TestClient(
    app,
    base_url="https://testserver",
    headers={"Origin": "http://localhost:5173"},
) as client:
    token = None

    try:
        login = client.post("/login", json={
            "username": username,
            "password": password,
        })

        assert login.status_code == 200, (
            f"Login failed: HTTP {login.status_code}"
        )

        token = client.cookies.get("session_token")
        assert token, "Session cookie missing"

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = mongo_db.sessions.find_one(
            {"_id": token_hash},
            {"expires_at": 1},
        )
        assert session and "expires_at" in session

        expires_at = session["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        token_headers = {"Cookie": f"session_token={token}"}

        valid = client.get("/incidents/mine", headers=token_headers)
        assert valid.status_code == 200
        print("PASS: A valid session allows access")

        # Advance only the time used by get_current_user().
        with patch("src.verifySession.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = (
                expires_at + timedelta(seconds=1)
            )

            expired = client.get(
                "/incidents/mine",
                headers=token_headers,
            )

        assert expired.status_code == 401, (
            f"Expired session was not rejected: HTTP {expired.status_code}"
        )
        print("PASS: Session is rejected after its expiration time")

        forged_token = secrets.token_urlsafe(32)
        forged = client.get(
            "/incidents/mine",
            headers={"Cookie": f"session_token={forged_token}"},
        )

        assert forged.status_code == 401, (
            f"Forged token was not rejected: HTTP {forged.status_code}"
        )
        print("PASS: A forged session token is rejected")

        print("\nAll session-validation checks passed.")

    finally:
        if token:
            client.post(
                "/logout",
                headers={"Cookie": f"session_token={token}"},
            )