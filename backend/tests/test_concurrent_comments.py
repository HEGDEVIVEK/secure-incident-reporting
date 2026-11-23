from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api import app


WORKERS = 5


def main():
    marker = uuid4().hex[:10]

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
            assert response.status_code == 200, "Reviewer login failed"

            account = response.json()["user"]
            assert account["role"] == "reviewer", "Use a Reviewer account"

            token = client.cookies.get("session_token")
            assert token, "Session cookie missing"

            # Your API permits any authenticated account to submit incidents.
            response = client.post(
                "/add_incidents",
                json={
                    "title": f"TEST - Concurrent comments {marker}",
                    "description": "Synthetic concurrent-write test.",
                    "priority": "medium",
                },
            )
            assert response.status_code == 201, (
                f"Incident creation failed: HTTP {response.status_code}"
            )
            incident_id = response.json()["id"]
            print(f"\nTest incident ID: {incident_id}")

            texts = [
                f"Concurrent comment {number + 1} - {marker}"
                for number in range(WORKERS)
            ]
            gate = Barrier(WORKERS)

            def submit_comment(number):
                # Each thread gets its own client, using the test session.
                with TestClient(
                    app,
                    base_url="https://testserver",
                    headers={"Origin": "http://localhost:5173"},
                ) as worker:
                    gate.wait(timeout=30)

                    response = worker.post(
                        f"/incidents/{incident_id}/comments",
                        headers={"Cookie": f"session_token={token}"},
                        json={"text": texts[number]},
                    )

                    assert response.status_code == 201, (
                        f"Comment {number + 1} failed: "
                        f"HTTP {response.status_code}"
                    )

                    return response.json()["id"]

            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                returned_ids = list(pool.map(submit_comment, range(WORKERS)))

            print(f"PASS: All {WORKERS} concurrent requests succeeded")

            assert len(set(returned_ids)) == WORKERS, (
                "Different comments received duplicate IDs"
            )
            print("PASS: Each comment has a distinct ID")

            response = client.get("/incidents")
            assert response.status_code == 200

            incident = next(
                (
                    item for item in response.json()
                    if item["id"] == incident_id
                ),
                None,
            )
            assert incident is not None, "Test incident not found"

            comments = incident.get("comments", [])
            assert len(comments) == WORKERS, (
                f"Expected {WORKERS} saved comments, found {len(comments)}"
            )
            assert {comment["id"] for comment in comments} == set(returned_ids)
            print("PASS: Every successful comment was saved exactly once")

            assert {comment["text"] for comment in comments} == set(texts), (
                "Comment text was lost or overwritten"
            )
            print("PASS: No comment text was lost or overwritten")

            assert all(
                comment["username"] == account["username"]
                for comment in comments
            )
            assert incident["status"] == "open"
            print("PASS: Comment authors and incident status remain correct")

            print("\nAll concurrent-comment checks passed.")

        finally:
            try:
                response = client.post("/logout")
                if response.status_code != 200:
                    print("Cleanup warning: logout failed")
            except Exception:
                print("Cleanup warning: could not log out")


if __name__ == "__main__":
    main()