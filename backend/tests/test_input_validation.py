from getpass import getpass

from fastapi.testclient import TestClient

from src.api import app


def expect(response, status, label):
    assert response.status_code == status, (
        f"{label}: expected HTTP {status}, "
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
            # These inputs must be rejected before credential verification.
            login_cases = [
                (
                    "NoSQL-style username object rejected",
                    {
                        "username": {"$ne": None},
                        "password": "dummy123",
                    },
                ),
                (
                    "Password object rejected",
                    {
                        "username": "validation_test",
                        "password": {"$ne": None},
                    },
                ),
                (
                    "Unexpected login role field rejected",
                    {
                        "username": "validation_test",
                        "password": "dummy123",
                        "role": "admin",
                    },
                ),
                (
                    "Missing login password rejected",
                    {"username": "validation_test"},
                ),
            ]

            for label, payload in login_cases:
                response = client.post("/login", json=payload)
                expect(response, 422, label)

            print("\nEnter credentials for an active regular User account.")
            username = input("Username: ").strip()
            password = getpass("Password: ")

            response = client.post(
                "/login",
                json={"username": username, "password": password},
            )
            assert response.status_code == 200, "Test account login failed"
            assert response.json()["user"]["role"] == "user", (
                "Use a regular User account"
            )

            def own_incident_ids():
                response = client.get("/incidents/mine")
                assert response.status_code == 200, (
                    "Could not read the account's incidents"
                )
                return {item["id"] for item in response.json()}

            before_ids = own_incident_ids()

            base = {
                "title": "TEST - Invalid input must not be saved",
                "description": "Synthetic validation test.",
                "priority": "medium",
            }

            cases = [
                ("Empty title rejected", {"title": ""}),
                ("Whitespace-only title rejected", {"title": "   "}),
                ("Oversized title rejected", {"title": "A" * 201}),
                ("Empty description rejected", {"description": ""}),
                (
                    "Whitespace-only description rejected",
                    {"description": " \n\t "},
                ),
                (
                    "Oversized description rejected",
                    {"description": "A" * 5001},
                ),
                ("Unsupported priority rejected", {"priority": "urgent"}),
                (
                    "NoSQL-style title object rejected",
                    {"title": {"$ne": None}},
                ),
                (
                    "Description object rejected",
                    {"description": {"$gt": ""}},
                ),
                (
                    "Control character in title rejected",
                    {"title": "Invalid\x00title"},
                ),
                (
                    "Control character in description rejected",
                    {"description": "Invalid\x00description"},
                ),
                (
                    "Client-supplied incident status rejected",
                    {"status": "closed"},
                ),
                (
                    "Client-supplied owner rejected",
                    {"submitted_by_id": "000000000000000000000000"},
                ),
                (
                    "Client-supplied comments rejected",
                    {"comments": [{"text": "Injected comment"}]},
                ),
            ]

            for label, changes in cases:
                response = client.post(
                    "/add_incidents",
                    json={**base, **changes},
                )
                expect(response, 422, label)

            missing_description = {
                "title": base["title"],
                "priority": base["priority"],
            }
            expect(
                client.post("/add_incidents", json=missing_description),
                422,
                "Missing required description rejected",
            )

            expect(
                client.post(
                    "/add_incidents",
                    content='{"title":',
                    headers={"Content-Type": "application/json"},
                ),
                422,
                "Malformed JSON rejected",
            )

            after_ids = own_incident_ids()
            assert after_ids == before_ids, (
                "Incident records changed during invalid-input testing"
            )
            print("PASS: Rejected submissions created no incidents")

            expect(
                client.get("/incidents/mine"),
                200,
                "Valid authenticated requests still work after invalid inputs",
            )

            print("\nAll input-validation checks in this script passed.")

        finally:
            try:
                response = client.post("/logout")
                if response.status_code != 200:
                    print("Cleanup warning: logout failed")
            except Exception:
                print("Cleanup warning: could not log out")


if __name__ == "__main__":
    main()