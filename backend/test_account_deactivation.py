from getpass import getpass

from fastapi.testclient import TestClient

from src.api import app

admin_name = input("Admin username: ").strip()
admin_password = getpass("Admin password: ")

user_name = input("Regular test username: ").strip()
user_password = getpass("Current password for that user: ")


def login(client, username, password):
    return client.post("/login", json={
        "username": username,
        "password": password,
    })


def set_active(client, user_id, active):
    return client.patch(
        f"/users/{user_id}/status-role",
        json={"role": "user", "is_active": active},
    )


tokens = []
user_id = None
restore_needed = False

with (
    TestClient(app, base_url="https://testserver") as admin_client,
    TestClient(app, base_url="https://testserver") as user_client,
):
    try:
        admin_login = login(admin_client, admin_name, admin_password)
        assert admin_login.status_code == 200, "Admin login failed"
        admin_account = admin_login.json()["user"]
        assert admin_account["role"] == "admin", "Use an Admin account"

        # Create two independent sessions for the regular user.
        for _ in range(2):
            user_client.cookies.clear()
            user_login = login(user_client, user_name, user_password)
            assert user_login.status_code == 200, "User login failed"

            account = user_login.json()["user"]
            assert account["role"] == "user", "Use a regular User account"
            user_id = account["id"]
            assert user_id != admin_account["id"]

            token = user_client.cookies.get("session_token")
            assert token, "Session cookie missing"
            tokens.append(token)

            assert user_client.get("/incidents/mine").status_code == 200

        assert len(set(tokens)) == 2
        print("PASS: Two user sessions work before deactivation")

        # Set this first so cleanup attempts restoration if a test fails.
        restore_needed = True
        deactivated = set_active(admin_client, user_id, False)
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False
        print("PASS: Admin can deactivate the test account")

        for token in tokens:
            response = user_client.get(
                "/incidents/mine",
                headers={"Cookie": f"session_token={token}"},
            )
            assert response.status_code == 401

        print("PASS: Both existing sessions are blocked")

        blocked_login = login(user_client, user_name, user_password)
        assert blocked_login.status_code == 401
        print("PASS: The inactive account cannot log in")

        reactivated = set_active(admin_client, user_id, True)
        assert reactivated.status_code == 200
        assert reactivated.json()["is_active"] is True
        restore_needed = False
        print("PASS: Admin can reactivate the account")

        for token in tokens:
            response = user_client.get(
                "/incidents/mine",
                headers={"Cookie": f"session_token={token}"},
            )
            assert response.status_code == 401

        print("PASS: Reactivation does not revive old sessions")

        user_client.cookies.clear()
        fresh_login = login(user_client, user_name, user_password)
        assert fresh_login.status_code == 200
        assert user_client.get("/incidents/mine").status_code == 200
        print("PASS: A fresh login works after reactivation")

    finally:
        try:
            if restore_needed and user_id:
                restored = set_active(admin_client, user_id, True)
                assert restored.status_code == 200, (
                    "Cleanup could not reactivate the account. "
                    "Reactivate it through the admin dashboard."
                )
                print("Cleanup: Test account reactivated")
        finally:
            cleanup_tokens = set(tokens)
            current_token = user_client.cookies.get("session_token")
            if current_token:
                cleanup_tokens.add(current_token)

            for token in cleanup_tokens:
                user_client.post(
                    "/logout",
                    headers={"Cookie": f"session_token={token}"},
                )

            admin_client.post("/logout")

print("\nAll account-deactivation checks passed.")