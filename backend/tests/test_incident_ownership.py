import secrets
from getpass import getpass

from fastapi.testclient import TestClient

from src.api import app


def sign_in(client, label):
    print(f"\nEnter credentials for regular User {label}")
    username = input("Username: ").strip()
    password = getpass("Password: ")

    response = client.post("/login", json={
        "username": username,
        "password": password,
    })

    assert response.status_code == 200, (
        f"User {label} login failed: HTTP {response.status_code}"
    )

    account = response.json()["user"]
    assert account["role"] == "user", "Use a regular User account"
    return account


run_id = secrets.token_hex(4)

with (
    TestClient(app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"}, ) as client_a,
    TestClient(app, base_url="https://testserver", headers={"Origin": "http://localhost:5173"},) as client_b,
):
    try:
        account_a = sign_in(client_a, "A")
        account_b = sign_in(client_b, "B")

        assert account_a["id"] != account_b["id"], (
            "Use two different accounts"
        )

        created_ids = []

        for client, label in ((client_a, "A"), (client_b, "B")):
            response = client.post("/add_incidents", json={
                "title": f"Ownership test {label} - {run_id}",
                "description": "Synthetic incident for access-control testing.",
                "priority": "low",
            })

            assert response.status_code == 201, (
                f"Incident creation failed: HTTP {response.status_code}"
            )
            created_ids.append(response.json()["id"])

        incident_a, incident_b = created_ids
        print("PASS: Both users can submit an incident")

        response_a = client_a.get("/incidents/mine")
        assert response_a.status_code == 200
        visible_a = {item["id"] for item in response_a.json()}

        assert incident_a in visible_a, "User A cannot see their own incident"
        assert incident_b not in visible_a, "User A can see User B's incident"
        print("PASS: User A sees their incident and cannot see User B's incident")

        response_b = client_b.get("/incidents/mine")
        assert response_b.status_code == 200
        visible_b = {item["id"] for item in response_b.json()}

        assert incident_b in visible_b, "User B cannot see their own incident"
        assert incident_a not in visible_b, "User B can see User A's incident"
        print("PASS: User B sees their incident and cannot see User A's incident")

        print("Test incident A:", incident_a)
        print("Test incident B:", incident_b)

    finally:
        client_a.post("/logout")
        client_b.post("/logout")

print("\nAll incident-ownership checks passed.")