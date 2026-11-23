from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
from secrets import token_urlsafe
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api import app


def expect(response, status, label):
    assert response.status_code == status, (
        f"{label}: expected HTTP {status}, "
        f"received HTTP {response.status_code}"
    )


def main():
    test_username = f"concurrent_{uuid4().hex[:10]}"
    test_password = token_urlsafe(9)
    user_id = None

    with (
        TestClient(app, base_url="https://testserver",  headers={"Origin": "http://localhost:5173"},) as admin,
        TestClient(app, base_url="https://testserver",  headers={"Origin": "http://localhost:5173"},) as user,
    ):
        try:
            print("Enter credentials for an active Admin account.")
            username = input("Admin username: ").strip()
            password = getpass("Admin password: ")

            response = admin.post(
                "/login",
                json={"username": username, "password": password},
            )
            expect(response, 200, "Admin login")
            assert response.json()["user"]["role"] == "admin"

            admin_token = admin.cookies.get("session_token")
            assert admin_token, "Admin session cookie missing"

            response = admin.post(
                "/add_users",
                json={
                    "username": test_username,
                    "password": test_password,
                    "role": "user",
                },
            )
            expect(response, 201, "Create temporary account")
            user_id = response.json()["id"]

            response = user.post(
                "/login",
                json={
                    "username": test_username,
                    "password": test_password,
                },
            )
            expect(response, 200, "Temporary account login")
            original_token = user.cookies.get("session_token")
            assert original_token

            expect(
                user.get("/incidents/mine"),
                200,
                "Original session access",
            )
            print("PASS: Temporary account has a working session")

            updates = [
                {"role": "reviewer", "is_active": True},
                {"role": "user", "is_active": False},
            ]
            gate = Barrier(2)

            def update_account(payload):
                with TestClient(
                    app,
                    base_url="https://testserver",
                    headers={"Origin": "http://localhost:5173"},
                ) as worker:
                    gate.wait(timeout=30)

                    response = worker.patch(
                        f"/users/{user_id}/status-role",
                        headers={
                            "Cookie": f"session_token={admin_token}"
                        },
                        json=payload,
                    )
                    expect(response, 200, "Concurrent account update")

                    saved = response.json()
                    assert saved["role"] == payload["role"]
                    assert saved["is_active"] is payload["is_active"]

            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(update_account, updates))

            print("PASS: Both simultaneous account updates succeeded")

            response = admin.get("/list_users")
            expect(response, 200, "Read final account state")

            account = next(
                item for item in response.json()
                if item["id"] == user_id
            )
            final_state = (account["role"], account["is_active"])

            assert final_state in {
                ("reviewer", True),
                ("user", False),
            }, "Final account contains an unexpected combination of fields"

            print("PASS: Final role/status matches one complete update")
            print(f"Final state before cleanup: {final_state}")

            # Deactivation occurs in either execution order.
            # A later reactivation must not revive the original session.
            response = user.get(
                "/incidents/mine",
                headers={
                    "Cookie": f"session_token={original_token}"
                },
            )
            expect(response, 401, "Reject original session")
            print("PASS: Original session remains invalid after deactivation")

            response = user.post(
                "/login",
                json={
                    "username": test_username,
                    "password": test_password,
                },
            )

            if account["is_active"]:
                expect(response, 200, "Fresh login for active account")
                assert response.json()["user"]["role"] == "reviewer"

                expect(
                    user.get("/incidents"),
                    200,
                    "Fresh reviewer access",
                )
                expect(
                    user.get("/list_users"),
                    403,
                    "Reviewer cannot access admin features",
                )
                print("PASS: Fresh login has the final reviewer permissions")
            else:
                expect(response, 401, "Inactive account login")
                print("PASS: Inactive account cannot log in")

            print("\nAll concurrent-account checks passed.")

        finally:
            try:
                if user_id:
                    response = admin.patch(
                        f"/users/{user_id}/status-role",
                        json={"role": "user", "is_active": False},
                    )
                    expect(response, 200, "Cleanup: deactivate test account")
                    print(f"Cleanup: Test account {test_username} deactivated")
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