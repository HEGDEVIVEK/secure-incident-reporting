from getpass import getpass
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

import src.api as api_module


def main():
    real_db = api_module.mongo_db
    title = f"TEST - Rollback {uuid4().hex}"

    with TestClient(
        api_module.app,
        base_url="https://testserver",
    ) as client:
        try:
            print("Enter credentials for an active regular User account.")
            username = input("Username: ").strip()
            password = getpass("Password: ")

            response = client.post(
                "/login",
                json={"username": username, "password": password},
            )
            assert response.status_code == 200, "Login failed"
            assert response.json()["user"]["role"] == "user", (
                "Use a regular User account"
            )

            assert real_db.incidents.find_one({"title": title}) is None

            failed_audit_insert = Mock(
                side_effect=RuntimeError("Simulated audit insertion failure")
            )

            # Incident writes still use the REAL MongoDB collection.
            # Only audit insertion is replaced with a deliberate failure.
            test_db = SimpleNamespace(
                incidents=real_db.incidents,
                audit_logs=SimpleNamespace(
                    insert_one=failed_audit_insert
                ),
            )

            with patch.object(api_module, "mongo_db", test_db):
                response = client.post(
                    "/add_incidents",
                    json={
                        "title": title,
                        "description": "Synthetic transaction rollback test.",
                        "priority": "medium",
                    },
                )

            # The patch is now removed; normal database access is restored.
            failed_audit_insert.assert_called_once()
            print("PASS: Incident creation reached the failing audit operation")

            assert response.status_code == 500, (
                f"Expected HTTP 500, received {response.status_code}"
            )
            assert response.json()["detail"] == (
                "Something went wrong. Please try again."
            )
            assert "Simulated audit insertion failure" not in response.text
            print("PASS: Failure returns a friendly error without internal details")

            saved_incident = real_db.incidents.find_one({"title": title})
            assert saved_incident is None, (
                f"ROLLBACK FAILED: An incident remains with title {title}"
            )
            print("PASS: MongoDB rolled back the incident insertion")

            response = client.get("/incidents/mine")
            assert response.status_code == 200, (
                "Authenticated requests stopped working after the failure"
            )
            assert all(
                item["title"] != title for item in response.json()
            )
            print("PASS: User cannot see an incident from the failed operation")
            print("PASS: Application still handles authenticated requests")

            print("\nIncident-creation rollback checks passed.")

        finally:
            try:
                response = client.post("/logout")
                if response.status_code != 200:
                    print("Cleanup warning: logout failed")
            except Exception:
                print("Cleanup warning: could not log out")


if __name__ == "__main__":
    main()