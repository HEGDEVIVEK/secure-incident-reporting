from getpass import getpass

from bson import ObjectId
from fastapi.testclient import TestClient

from src.api import app

test_id = str(ObjectId())
passed = 0

# These requests target synthetic data or a fresh, nonexistent ID.
admin_operations = [
    ("GET", "/list_users", None, 403),

    ("POST", "/add_users", {
        "username": f"rbac_check_{test_id}",
        "password": "TestPassword123",
        "role": "user",
    }, 403),

    ("PATCH", f"/users/{test_id}/status-role", {
        "role": "user",
        "is_active": True,
    }, 403),
]

for expected_role in ("user", "reviewer", "admin"):
    print(f"\nEnter credentials for an active {expected_role} test account.")
    username = input("Username: ").strip()
    password = getpass("Password: ")

    with TestClient(app, base_url="https://testserver") as client:
        try:
            login = client.post("/login", json={
                "username": username,
                "password": password,
            })

            assert login.status_code == 200, (
                f"Login failed: HTTP {login.status_code}"
            )

            account = login.json()["user"]

            assert account["role"] == expected_role, (
                f"Please use an account with the '{expected_role}' role."
            )

            if expected_role == "user":
                checks = [
                    ("GET", "/incidents/mine", None, 200),
                    *admin_operations,
                    ("GET", "/incidents", None, 403),

                    ("POST", f"/incidents/{test_id}/comments", {
                        "text": "Synthetic permission test",
                    }, 403),

                    ("PATCH", f"/incidents/{test_id}/status", {
                        "status": "closed",
                    }, 403),
                ]

            elif expected_role == "reviewer":
                checks = [
                    ("GET", "/incidents", None, 200),
                    *admin_operations,
                ]

            else:
                checks = [
                    ("GET", "/list_users", None, 200),
                    ("GET", "/incidents", None, 200),

                    # Even a request retaining the current values must
                    # be rejected by the existing self-update restriction.
                    ("PATCH", f"/users/{account['id']}/status-role", {
                        "role": "admin",
                        "is_active": True,
                    }, 403),
                ]

            for method, path, payload, expected_status in checks:
                options = {"json": payload} if payload is not None else {}
                response = client.request(method, path, **options)

                assert response.status_code == expected_status, (
                    f"FAIL [{expected_role}]: {method} {path} — "
                    f"expected {expected_status}, "
                    f"received {response.status_code}"
                )

                passed += 1
                print(
                    f"PASS [{expected_role}]: "
                    f"{method} {path} -> {response.status_code}"
                )

        finally:
            client.post("/logout")

print(f"\nAll {passed} role-permission checks passed.")