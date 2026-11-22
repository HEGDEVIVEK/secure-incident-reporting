from getpass import getpass

from fastapi.testclient import TestClient

from src.api import app

username = input("Regular test account username: ").strip()
old_password = getpass("Current password: ")
new_password = getpass("New password: ")

assert new_password != old_password, "Choose a different new password"


def login(client, password):
    return client.post("/login", json={
        "username": username,
        "password": password,
    })


def change_password(client, current_password):
    return client.post("/update-password", json={
        "username": username,
        "current_password": current_password,
        "new_password": new_password,
    })


session_tokens = []

with TestClient(
    app,
    base_url="https://testserver",
    headers={"Origin": "http://localhost:5173"},
) as client:
    try:
        # Create two independent sessions for the same account.
        for _ in range(2):
            client.cookies.clear()
            response = login(client, old_password)

            assert response.status_code == 200, (
                f"Login failed: HTTP {response.status_code}"
            )
            assert response.json()["user"]["role"] == "user", (
                "Use a regular User account for this test"
            )

            token = client.cookies.get("session_token")
            assert token, "Session cookie missing"
            session_tokens.append(token)

            assert client.get("/incidents/mine").status_code == 200

        assert len(set(session_tokens)) == 2
        print("PASS: Two independent sessions work before the password change")

        # Make a guaranteed-different current password.
        replacement = "X" if old_password[-1] != "X" else "Y"
        wrong_password = old_password[:-1] + replacement

        rejected = change_password(client, wrong_password)
        assert rejected.status_code == 401
        print("PASS: Password change rejects an incorrect current password")

        changed = change_password(client, old_password)
        assert changed.status_code == 200, (
            f"Password change failed: HTTP {changed.status_code}"
        )
        print("PASS: Password changes successfully with correct credentials")

        for token in session_tokens:
            replay = client.get(
                "/incidents/mine",
                headers={"Cookie": f"session_token={token}"},
            )
            assert replay.status_code == 401, (
                "An old session remained usable after the password change"
            )

        print("PASS: Both old sessions are rejected after the password change")

        client.cookies.clear()
        assert login(client, old_password).status_code == 401
        print("PASS: The old password no longer works")

        fresh_login = login(client, new_password)
        assert fresh_login.status_code == 200
        assert client.get("/incidents/mine").status_code == 200
        print("PASS: The new password creates a working session")

    finally:
        # Clean up any sessions created by this test.
        cleanup_tokens = set(session_tokens)
        current_token = client.cookies.get("session_token")

        if current_token:
            cleanup_tokens.add(current_token)

        for token in cleanup_tokens:
            client.post(
                "/logout",
                headers={"Cookie": f"session_token={token}"},
            )

print("\nAll password-change checks passed.")