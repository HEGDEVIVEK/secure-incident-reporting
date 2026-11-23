from getpass import getpass

from fastapi.testclient import TestClient

from src.api import app


def check(response, expected, action):
    assert response.status_code == expected, (
        f"{action}: expected HTTP {expected}, "
        f"received HTTP {response.status_code}"
    )


def login(client, role):
    print(f"\nEnter credentials for an active {role} test account.")
    username = input("Username: ").strip()
    password = getpass("Password: ")

    response = client.post(
        "/login",
        json={"username": username, "password": password},
    )
    check(response, 200, f"{role} login")

    account = response.json()["user"]
    assert account["role"] == role, f"Use an account with role '{role}'"
    return account


def main():
    needs_restore = False
    user_id = None

    with (
        TestClient(app, base_url="https://testserver",  headers={"Origin": "http://localhost:5173"},) as admin,
        TestClient(app, base_url="https://testserver",  headers={"Origin": "http://localhost:5173"},) as user,
    ):
        try:
            admin_account = login(admin, "admin")
            user_account = login(user, "user")

            user_id = user_account["id"]
            assert user_id != admin_account["id"]

            original_token = user.cookies.get("session_token")
            assert original_token, "Session cookie missing"

            def same_session_get(path):
                # Explicitly reuse the token issued before the role changes.
                return user.get(
                    path,
                    headers={"Cookie": f"session_token={original_token}"},
                )

            check(
                same_session_get("/incidents/mine"),
                200,
                "Read own incidents",
            )
            check(
                same_session_get("/incidents"),
                403,
                "Regular user cannot read all incidents",
            )
            print("PASS: Original session has regular-user permissions")

            # Set this before the request so cleanup also handles
            # a response failure after a successful database change.
            needs_restore = True

            response = admin.patch(
                f"/users/{user_id}/status-role",
                json={"role": "reviewer", "is_active": True},
            )
            check(response, 200, "Promote test account")
            assert response.json()["role"] == "reviewer"
            print("PASS: Admin changes the test account to Reviewer")

            check(
                same_session_get("/incidents"),
                200,
                "Existing session receives reviewer access",
            )
            print("PASS: Same session gains reviewer access without login")

            check(
                same_session_get("/list_users"),
                403,
                "Reviewer cannot access admin functionality",
            )
            print("PASS: Promoted reviewer still cannot access admin features")

            response = admin.patch(
                f"/users/{user_id}/status-role",
                json={"role": "user", "is_active": True},
            )
            check(response, 200, "Restore regular-user role")
            assert response.json()["role"] == "user"
            needs_restore = False
            print("PASS: Admin restores the account to User")

            check(
                same_session_get("/incidents"),
                403,
                "Existing session loses reviewer access",
            )
            print("PASS: Same session immediately loses reviewer access")

            check(
                same_session_get("/incidents/mine"),
                200,
                "Regular-user access still works",
            )
            print("PASS: Same session can still read its own incidents")

            print("\nAll active-role-change checks passed.")

        finally:
            try:
                if needs_restore and user_id:
                    response = admin.patch(
                        f"/users/{user_id}/status-role",
                        json={"role": "user", "is_active": True},
                    )
                    check(response, 200, "Cleanup: restore User role")
                    print("Cleanup: Test account restored to User")
            finally:
                for label, client in (("user", user), ("admin", admin)):
                    try:
                        response = client.post("/logout")
                        if response.status_code != 200:
                            print(f"Cleanup warning: {label} logout failed")
                    except Exception:
                        print(f"Cleanup warning: could not log out {label}")


if __name__ == "__main__":
    main()