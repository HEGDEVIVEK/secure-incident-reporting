from contextlib import ExitStack
from getpass import getpass
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api import app


def expect_status(response, expected, action):
    assert response.status_code == expected, (
        f"{action}: expected HTTP {expected}, "
        f"received HTTP {response.status_code}"
    )


def sign_in(client, role):
    print(f"\nEnter credentials for an active {role} test account.")
    username = input("Username: ").strip()
    password = getpass("Password: ")

    response = client.post(
        "/login",
        json={"username": username, "password": password},
    )
    expect_status(response, 200, f"{role} login")

    account = response.json()["user"]
    assert account["role"] == role, f"Use an account with role '{role}'"
    return account


def find_incident(client, endpoint, incident_id):
    response = client.get(endpoint)
    expect_status(response, 200, f"Read {endpoint}")

    incident = next(
        (item for item in response.json() if item["id"] == incident_id),
        None,
    )
    assert incident is not None, f"Test incident missing from {endpoint}"
    return incident


def main():
    marker = uuid4().hex[:10]
    payload = {
        "title": f"TEST - Incident workflow {marker}",
        "description": "Synthetic incident for automated workflow testing.",
        "priority": "medium",
    }

    with ExitStack() as stack:
        clients = {
            role: stack.enter_context(
                TestClient(app, base_url="https://testserver")
            )
            for role in ("user", "reviewer", "admin")
        }

        try:
            accounts = {
                role: sign_in(client, role)
                for role, client in clients.items()
            }

            assert len({a["id"] for a in accounts.values()}) == 3, (
                "Use three different accounts"
            )

            user = clients["user"]
            reviewer = clients["reviewer"]
            admin = clients["admin"]

            response = user.post("/add_incidents", json=payload)
            expect_status(response, 201, "Create test incident")
            incident_id = response.json()["id"]
            assert response.json()["status"] == "open"

            print(f"\nTest incident ID: {incident_id}")

            expected_comments = []

            def verify_visible_state(expected_status):
                """Check saved details and comments through all three roles."""
                for role, endpoint in (
                    ("user", "/incidents/mine"),
                    ("reviewer", "/incidents"),
                    ("admin", "/incidents"),
                ):
                    incident = find_incident(
                        clients[role], endpoint, incident_id
                    )

                    assert incident["status"] == expected_status, (
                        f"{role}: incorrect incident status"
                    )

                    for field, value in payload.items():
                        assert incident[field] == value, (
                            f"{role}: incident {field} changed unexpectedly"
                        )

                    comments = {
                        comment["id"]: comment
                        for comment in incident.get("comments", [])
                    }

                    for comment_id, text, author in expected_comments:
                        assert comment_id in comments, (
                            f"{role}: saved comment is missing"
                        )
                        assert comments[comment_id]["text"] == text, (
                            f"{role}: incorrect comment text"
                        )
                        assert comments[comment_id]["username"] == author, (
                            f"{role}: incorrect comment author"
                        )

            verify_visible_state("open")
            print("PASS: User, reviewer, and admin can see the open incident")

            response = reviewer.patch(
                f"/incidents/{incident_id}/status",
                json={"status": "under-review"},
            )
            expect_status(response, 200, "Start review")
            verify_visible_state("under-review")
            print("PASS: Reviewer starts review; all three roles see the update")

            for role, text in (
                ("reviewer", f"Reviewer investigation started - {marker}"),
                ("admin", f"Admin reviewed the incident - {marker}"),
            ):
                response = clients[role].post(
                    f"/incidents/{incident_id}/comments",
                    json={"text": text},
                )
                expect_status(response, 201, f"Add {role} comment")

                expected_comments.append(
                    (
                        response.json()["id"],
                        text,
                        accounts[role]["username"],
                    )
                )

                verify_visible_state("under-review")
                print(
                    f"PASS: {role.capitalize()} comment is saved "
                    "and visible to all three roles"
                )

            response = reviewer.patch(
                f"/incidents/{incident_id}/status",
                json={"status": "closed"},
            )
            expect_status(response, 200, "Close incident")
            verify_visible_state("closed")
            print(
                "PASS: Reviewer closes the incident; all three roles "
                "see Closed with both comments preserved"
            )

            print("\nAll incident-workflow checks passed.")

        finally:
            for role, client in clients.items():
                try:
                    response = client.post("/logout")
                    if response.status_code != 200:
                        print(f"Cleanup warning: {role} logout failed")
                except Exception:
                    print(f"Cleanup warning: could not log out {role}")


if __name__ == "__main__":
    main()