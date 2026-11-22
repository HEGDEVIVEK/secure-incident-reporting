import secrets

from fastapi.testclient import TestClient
from src.api import app

# 13 characters, so these still pass validation if you raise the minimum length later
WRONG_PASSWORD = "WrongPass#123"
NEW_PASSWORD = "NewPass#12345"
MAX_FAILURES = 5

# Random usernames keep this test independent of real accounts.
username = f"lockout_{secrets.token_hex(4)}"
other_username = f"lockout_{secrets.token_hex(4)}"

with TestClient(app) as client:
    for _ in range(MAX_FAILURES):
        response = client.post(
            "/login", json={"username": username, "password": WRONG_PASSWORD}
        )
        assert response.status_code == 401
    print(f"PASS: {MAX_FAILURES} wrong passwords are rejected with 401")

    locked = client.post(
        "/login", json={"username": username, "password": WRONG_PASSWORD}
    )
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) > 0
    print("PASS: the next attempt is locked out with 429 and a Retry-After header")

    change = client.post(
        "/update-password",
        json={
            "username": username,
            "current_password": WRONG_PASSWORD,
            "new_password": NEW_PASSWORD,
        },
    )
    assert change.status_code == 429
    print("PASS: password change is locked out too")

    other = client.post(
        "/login", json={"username": other_username, "password": WRONG_PASSWORD}
    )
    assert other.status_code == 401
    print("PASS: a different username is not affected")