from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api import app


def main():
    with TestClient(
    app,
    base_url="https://testserver",
    headers={"Origin": "http://localhost:5173"},
) as client:
        try:
            print("Enter credentials for an active Reviewer test account.")
            username = input("Username: ").strip()
            password = getpass("Password: ")

            response = client.post(
                "/login",
                json={"username": username, "password": password},
            )
            assert response.status_code == 200, "Login failed"
            assert response.json()["user"]["role"] == "reviewer"

            token = client.cookies.get("session_token")
            assert token, "Session cookie missing"

            payload = {
                "title": f"TEST - Concurrent status {uuid4().hex[:10]}",
                "description": "Synthetic concurrent status-update test.",
                "priority": "medium",
            }

            response = client.post("/add_incidents", json=payload)
            assert response.status_code == 201, "Incident creation failed"
            incident_id = response.json()["id"]
            assert response.json()["status"] == "open"

            gate = Barrier(2)
            requested_statuses = ["under-review", "closed"]

            def update_status(status):
                # Independent clients simulate simultaneous requests.
                # Both use the same authorized reviewer session.
                with TestClient(
                    app,
                    base_url="https://testserver",
                ) as worker:
                    gate.wait(timeout=30)

                    response = worker.patch(
                        f"/incidents/{incident_id}/status",
                        headers={"Cookie": f"session_token={token}"},
                        json={"status": status},
                    )

                    assert response.status_code == 200, (
                        f"Update to {status} failed: "
                        f"HTTP {response.status_code}"
                    )
                    assert response.json()["status"] == status
                    return status

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(update_status, requested_statuses))

            assert set(results) == set(requested_statuses)
            print("PASS: Both simultaneous status-update requests succeeded")

            response = client.get("/incidents")
            assert response.status_code == 200

            matches = [
                item for item in response.json()
                if item["id"] == incident_id
            ]
            assert len(matches) == 1, "Expected exactly one test incident"
            saved = matches[0]

            assert saved["status"] in requested_statuses, (
                "Final status does not match either requested update"
            )
            print("PASS: Final status matches one of the concurrent updates")

            for field, value in payload.items():
                assert saved[field] == value, (
                    f"Status updates unexpectedly changed {field}"
                )

            assert saved.get("comments", []) == []
            print("PASS: Other incident fields remain unchanged")

            print(f"\nTest incident ID: {incident_id}")
            print(f"Final status: {saved['status']}")
            print("Concurrent-status API checks passed.")

        finally:
            try:
                response = client.post("/logout")
                if response.status_code != 200:
                    print("Cleanup warning: logout failed")
            except Exception:
                print("Cleanup warning: could not log out")


if __name__ == "__main__":
    main()