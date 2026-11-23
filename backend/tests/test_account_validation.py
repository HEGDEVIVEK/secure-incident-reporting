from getpass import getpass
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api import app


def check(response, expected, label):
    assert response.status_code == expected, (
        f"{label}: expected HTTP {expected}, "
        f"received HTTP {response.status_code}"
    )
    print(f"PASS: {label}")


def read_users(client):
    response = client.get("/list_users")
    assert response.status_code == 200, "Could not read user accounts"
    return response.json()


def main():
    restore_needed = False
    target = None

    with TestClient(app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"},) as admin:
        try:
            print("Enter credentials for an active Admin account.")
            username = input("Admin username: ").strip()
            password = getpass("Admin password: ")

            response = admin.post(
                "/login",
                json={"username": username, "password": password},
            )
            assert response.status_code == 200, "Admin login failed"
            assert response.json()["user"]["role"] == "admin", (
                "Use an Admin account"
            )

            before_users = read_users(admin)
            before_ids = {user["id"] for user in before_users}

            target_name = input(
                "\nExisting active regular test username (e.g. user1): "
            ).strip()

            target = next(
                (
                    user for user in before_users
                    if user["username"] == target_name
                ),
                None,
            )
            assert target is not None, "Test account not found"
            assert target["role"] == "user", "Choose a regular User account"
            assert target["is_active"] is True, "Choose an active account"

            base = {
                "username": f"validation_{uuid4().hex[:10]}",
                "password": "TestOnly123!",
                "role": "user",
            }

            creation_cases = [
                ("Short username rejected", {"username": "ab"}),
                ("Oversized username rejected", {"username": "a" * 65}),
                ("Spaces in username rejected", {"username": "test user"}),
                (
                    "NoSQL-style username object rejected",
                    {"username": {"$ne": None}},
                ),
                (
                    "Password under 12 characters rejected",
                    {"password": "Short1!abcd"},  # 11 characters
                ),
                (
                    "Password exceeding 128 characters rejected",
                    {"password": "a" * 129},
                ),
                ("Unknown role rejected", {"role": "superadmin"}),
                (
                    "Unexpected account field rejected",
                    {"is_active": False},
                ),
                (
                    "Client-supplied password hash rejected",
                    {"password_hash": "forged_hash"},
                ),
            ]

            for label, changes in creation_cases:
                check(
                    admin.post("/add_users", json={**base, **changes}),
                    422,
                    label,
                )

            after_users = read_users(admin)
            assert {user["id"] for user in after_users} == before_ids, (
                "Rejected account-creation requests changed the user list"
            )
            print("PASS: Invalid account submissions created no users")

            original = {
                "role": target["role"],
                "is_active": target["is_active"],
            }

            update_cases = [
                ("Unknown updated role rejected", {"role": "superadmin"}),
                (
                    "String Boolean rejected",
                    {"is_active": "false"},
                ),
                (
                    "Numeric Boolean rejected",
                    {"is_active": 1},
                ),
                (
                    "Unexpected update field rejected",
                    {"password_hash": "forged_hash"},
                ),
            ]

            for label, changes in update_cases:
                # Restore the original role/status if an invalid update
                # is unexpectedly accepted or its outcome is uncertain.
                restore_needed = True

                response = admin.patch(
                    f"/users/{target['id']}/status-role",
                    json={**original, **changes},
                )
                check(response, 422, label)

                current = next(
                    user for user in read_users(admin)
                    if user["id"] == target["id"]
                )
                assert current == target, (
                    "Rejected update changed the test account"
                )

                restore_needed = False

            print("PASS: Test account remains active with its original role")
            print("\nAll account-validation checks passed.")

        finally:
            try:
                if restore_needed and target:
                    response = admin.patch(
                        f"/users/{target['id']}/status-role",
                        json={
                            "role": target["role"],
                            "is_active": target["is_active"],
                        },
                    )
                    assert response.status_code == 200, (
                        "Cleanup failed: check the test account's role/status"
                    )
                    print("Cleanup: Original role and status restored")
            finally:
                try:
                    response = admin.post("/logout")
                    if response.status_code != 200:
                        print("Cleanup warning: admin logout failed")
                except Exception:
                    print("Cleanup warning: could not log out admin")


if __name__ == "__main__":
    main()