from getpass import getpass
from secrets import token_hex

from fastapi.testclient import TestClient

from src.api import app


def check(response, expected, label):
    assert response.status_code == expected, (
        f"{label}: expected HTTP {expected}, "
        f"received HTTP {response.status_code}"
    )
    print(f"PASS: {label}")


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
            assert response.status_code == 200, "Reviewer login failed"
            assert response.json()["user"]["role"] == "reviewer", (
                "Use a Reviewer account"
            )

            response = client.get("/incidents")
            assert response.status_code == 200
            incidents = response.json()

            # Reuse the synthetic incident from the previous workflow test.
            incident = next(
                (
                    item for item in incidents
                    if item["title"].startswith("TEST - Incident workflow")
                ),
                None,
            )
            assert incident is not None, (
                "Workflow test incident not found. "
                "Run test_incident_workflow.py first."
            )

            incident_id = incident["id"]
            original_status = incident["status"]
            original_comments = incident.get("comments", [])

            print(f"\nTesting incident: {incident_id}")

            comment_cases = [
                ("Empty comment rejected", {"text": ""}),
                ("Whitespace-only comment rejected", {"text": " \n\t "}),
                ("Oversized comment rejected", {"text": "A" * 2001}),
                ("Missing comment text rejected", {}),
                (
                    "NoSQL-style comment object rejected",
                    {"text": {"$ne": None}},
                ),
                (
                    "Control character rejected",
                    {"text": "Invalid\x00comment"},
                ),
                (
                    "Forged comment author rejected",
                    {"text": "Synthetic test", "username": "admin"},
                ),
                (
                    "Client-supplied user ID rejected",
                    {
                        "text": "Synthetic test",
                        "user_id": "000000000000000000000000",
                    },
                ),
            ]

            for label, payload in comment_cases:
                check(
                    client.post(
                        f"/incidents/{incident_id}/comments",
                        json=payload,
                    ),
                    422,
                    label,
                )

            status_cases = [
                ("Unknown status rejected", {"status": "resolved"}),
                ("Empty status rejected", {"status": ""}),
                ("Missing status rejected", {}),
                (
                    "NoSQL-style status object rejected",
                    {"status": {"$ne": None}},
                ),
                (
                    "Unexpected status-update field rejected",
                    {"status": original_status, "role": "admin"},
                ),
            ]

            for label, payload in status_cases:
                check(
                    client.patch(
                        f"/incidents/{incident_id}/status",
                        json=payload,
                    ),
                    422,
                    label,
                )

            check(
                client.post(
                    "/incidents/not-an-object-id/comments",
                    json={"text": "Synthetic test"},
                ),
                422,
                "Malformed incident ID rejected for comments",
            )

            check(
                client.patch(
                    "/incidents/not-an-object-id/status",
                    json={"status": "open"},
                ),
                422,
                "Malformed incident ID rejected for status updates",
            )

            existing_ids = {item["id"] for item in incidents}
            missing_id = token_hex(12)
            while missing_id in existing_ids:
                missing_id = token_hex(12)

            check(
                client.post(
                    f"/incidents/{missing_id}/comments",
                    json={"text": "Synthetic test"},
                ),
                404,
                "Comment on a nonexistent incident returns 404",
            )

            check(
                client.patch(
                    f"/incidents/{missing_id}/status",
                    json={"status": "open"},
                ),
                404,
                "Status update on a nonexistent incident returns 404",
            )

            response = client.get("/incidents")
            assert response.status_code == 200
            saved = next(
                item for item in response.json()
                if item["id"] == incident_id
            )

            assert saved["status"] == original_status, (
                "Rejected requests changed the incident status"
            )
            assert saved.get("comments", []) == original_comments, (
                "Rejected requests changed the incident comments"
            )
            print("PASS: Incident status and comments remain unchanged")

            print("\nAll comment/status validation checks passed.")

        finally:
            try:
                response = client.post("/logout")
                if response.status_code != 200:
                    print("Cleanup warning: logout failed")
            except Exception:
                print("Cleanup warning: could not log out")


if __name__ == "__main__":
    main()