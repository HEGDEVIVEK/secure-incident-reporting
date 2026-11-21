import hashlib
from getpass import getpass
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from bson import ObjectId
from fastapi.testclient import TestClient

import src.api as api_module


def expect(response, status, label):
    assert response.status_code == status, (
        f"{label}: expected HTTP {status}, "
        f"received HTTP {response.status_code}"
    )


def login(client, role):
    print(f"\nEnter credentials for an active {role} account.")
    username = input("Username: ").strip()
    password = getpass("Password: ")

    response = client.post(
        "/login",
        json={"username": username, "password": password},
    )
    expect(response, 200, f"{role} login")
    assert response.json()["user"]["role"] == role


def main():
    real_db = api_module.mongo_db
    marker = uuid4().hex[:12]
    test_username = f"rollback_{marker}"
    rejected_username = f"rejected_{marker}"
    test_password = token_urlsafe(9)
    new_password = token_urlsafe(9)

    while new_password == test_password:
        new_password = token_urlsafe(9)

    incident_id = None
    admin_ready = False

    with (
        TestClient(api_module.app, base_url="https://testserver") as admin,
        TestClient(api_module.app, base_url="https://testserver") as reviewer,
        TestClient(api_module.app, base_url="https://testserver") as user,
    ):
        def fail_audit(client, method, path, payload):
            failed_insert = Mock(
                side_effect=RuntimeError("Simulated audit insertion failure")
            )

            # All business-data operations still use real MongoDB collections.
            test_db = SimpleNamespace(
                users=real_db.users,
                incidents=real_db.incidents,
                sessions=real_db.sessions,
                audit_logs=SimpleNamespace(insert_one=failed_insert),
            )

            with patch.object(api_module, "mongo_db", test_db):
                response = client.request(method, path, json=payload)

            failed_insert.assert_called_once()
            expect(response, 500, "Simulated audit failure")
            assert response.json()["detail"] == (
                "Something went wrong. Please try again."
            )

        try:
            login(admin, "admin")
            admin_ready = True
            login(reviewer, "reviewer")

            # 1. Failed audit insertion must roll back account creation.
            assert real_db.users.find_one(
                {"username": rejected_username}
            ) is None

            fail_audit(
                admin,
                "POST",
                "/add_users",
                {
                    "username": rejected_username,
                    "password": test_password,
                    "role": "user",
                },
            )

            assert real_db.users.find_one(
                {"username": rejected_username}
            ) is None, "Account creation was not rolled back"

            print("PASS: Account creation rolls back when audit insertion fails")

            # Create fixtures normally for the remaining checks.
            response = admin.post(
                "/add_users",
                json={
                    "username": test_username,
                    "password": test_password,
                    "role": "user",
                },
            )
            expect(response, 201, "Create test account")
            user_id = response.json()["id"]
            user_object_id = ObjectId(user_id)

            response = user.post(
                "/login",
                json={
                    "username": test_username,
                    "password": test_password,
                },
            )
            expect(response, 200, "Test account login")
            token = user.cookies.get("session_token")
            assert token
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            response = user.post(
                "/add_incidents",
                json={
                    "title": f"TEST - Remaining rollbacks {marker}",
                    "description": "Synthetic rollback verification.",
                    "priority": "medium",
                },
            )
            expect(response, 201, "Create test incident")
            incident_id = response.json()["id"]
            incident_object_id = ObjectId(incident_id)

            # 2–3. Comment and status changes must be rolled back.
            incident_cases = [
                (
                    "Comment creation",
                    "POST",
                    f"/incidents/{incident_id}/comments",
                    {"text": "This comment must be rolled back"},
                ),
                (
                    "Incident status change",
                    "PATCH",
                    f"/incidents/{incident_id}/status",
                    {"status": "closed"},
                ),
            ]

            for label, method, path, payload in incident_cases:
                before = real_db.incidents.find_one(
                    {"_id": incident_object_id}
                )
                assert before is not None

                fail_audit(reviewer, method, path, payload)

                after = real_db.incidents.find_one(
                    {"_id": incident_object_id}
                )
                assert after == before, f"{label} was not rolled back"
                print(f"PASS: {label} rolls back completely")

            # 4–6. Account changes and session deletions must roll back.
            account_cases = [
                (
                    "Role change",
                    admin,
                    "PATCH",
                    f"/users/{user_id}/status-role",
                    {"role": "reviewer", "is_active": True},
                ),
                (
                    "Account deactivation",
                    admin,
                    "PATCH",
                    f"/users/{user_id}/status-role",
                    {"role": "user", "is_active": False},
                ),
                (
                    "Password change",
                    user,
                    "POST",
                    "/update-password",
                    {
                        "username": test_username,
                        "current_password": test_password,
                        "new_password": new_password,
                    },
                ),
            ]

            for label, client, method, path, payload in account_cases:
                before_user = real_db.users.find_one(
                    {"_id": user_object_id}
                )
                before_session = real_db.sessions.find_one(
                    {"_id": token_hash}
                )
                assert before_user is not None
                assert before_session is not None

                fail_audit(client, method, path, payload)

                assert real_db.users.find_one(
                    {"_id": user_object_id}
                ) == before_user, f"{label}: account was not restored"

                assert real_db.sessions.find_one(
                    {"_id": token_hash}
                ) == before_session, f"{label}: session was not restored"

                expect(
                    user.get("/incidents/mine"),
                    200,
                    f"Session access after failed {label}",
                )

                print(
                    f"PASS: {label} rolls back; "
                    "account and original session remain unchanged"
                )

            print("\nAll remaining rollback checks passed.")

        finally:
            if incident_id:
                try:
                    response = reviewer.patch(
                        f"/incidents/{incident_id}/status",
                        json={"status": "closed"},
                    )
                    expect(response, 200, "Close test incident")
                    print("Cleanup: Test incident closed")
                except Exception:
                    print(f"Cleanup warning: Check incident {incident_id}")

            if admin_ready:
                for name in (test_username, rejected_username):
                    try:
                        account = real_db.users.find_one({"username": name})
                        if account:
                            response = admin.patch(
                                f"/users/{account['_id']}/status-role",
                                json={"role": "user", "is_active": False},
                            )
                            expect(response, 200, "Deactivate test account")
                            print(f"Cleanup: {name} deactivated")
                    except Exception:
                        print(f"Cleanup warning: Check test account {name}")

            for label, client in (
                ("user", user),
                ("reviewer", reviewer),
                ("admin", admin),
            ):
                try:
                    response = client.post("/logout")
                    if response.status_code != 200:
                        print(f"Cleanup warning: {label} logout failed")
                except Exception:
                    print(f"Cleanup warning: could not log out {label}")


if __name__ == "__main__":
    main()