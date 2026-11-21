import hashlib
import json
from contextlib import ExitStack
from getpass import getpass

from bson import ObjectId
from fastapi.testclient import TestClient

from src.api import app
from src.mongodb import mongo_db
from src.security import password_hasher


FORBIDDEN_FIELDS = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "session_token",
    "token_hash",
    "mongo_uri",
}

# Values that must never appear in these JSON response bodies.
protected_values = []


def check_response(response, label):
    assert response.status_code == 200, (
        f"{label}: expected HTTP 200, received {response.status_code}"
    )

    data = response.json()

    def inspect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                assert key.lower() not in FORBIDDEN_FIELDS, (
                    f"{label}: response contains a credential field"
                )
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(data)

    serialized = json.dumps(data)
    for secret in protected_values:
        assert secret not in serialized, (
            f"{label}: response exposes a stored hash or session token"
        )

    print(f"PASS: {label} contains no checked credential fields or secrets")


def main():
    with ExitStack() as stack:
        clients = {
            role: stack.enter_context(
                TestClient(app, base_url="https://testserver")
            )
            for role in ("user", "reviewer", "admin")
        }

        login_responses = {}

        try:
            for role, client in clients.items():
                print(f"\nEnter credentials for an active {role} account.")
                username = input("Username: ").strip()
                password = getpass("Password: ")

                response = client.post(
                    "/login",
                    json={"username": username, "password": password},
                )
                assert response.status_code == 200, f"{role} login failed"

                account = response.json()["user"]
                assert account["role"] == role, (
                    f"Use an account with role '{role}'"
                )
                login_responses[role] = response

                stored_user = mongo_db.users.find_one(
                    {"_id": ObjectId(account["id"])}
                )
                assert stored_user is not None

                stored_hash = stored_user.get("password_hash")
                assert isinstance(stored_hash, str)
                assert stored_hash.startswith("$argon2"), (
                    f"{role}: expected an Argon2 password hash"
                )
                assert stored_hash != password
                assert password_hasher.verify(password, stored_hash)

                for field in ("password", "current_password", "new_password"):
                    assert field not in stored_user, (
                        f"{role}: unexpected password field in user document"
                    )

                protected_values.append(stored_hash)
                print(
                    f"PASS: {role} password is stored as a working "
                    "Argon2 hash, with no checked plaintext password fields"
                )

                token = client.cookies.get("session_token")
                assert token, "Login did not issue a session cookie"
                protected_values.append(token)

                token_hash = hashlib.sha256(token.encode()).hexdigest()
                protected_values.append(token_hash)

                session = mongo_db.sessions.find_one({"_id": token_hash})
                assert session is not None, (
                    f"{role}: hashed session record not found"
                )
                assert session["user_id"] == ObjectId(account["id"])
                assert token not in json.dumps(session, default=str), (
                    f"{role}: raw session token is stored in its session record"
                )

                print(
                    f"PASS: {role} session uses the token hash; "
                    "its database record does not contain the raw token"
                )

            # Check JSON bodies only. The login Set-Cookie header
            # intentionally carries the session token to the client.
            for role, response in login_responses.items():
                check_response(response, f"{role} login response")

            checks = [
                ("user", "/incidents/mine", "User incident list"),
                ("reviewer", "/incidents", "Reviewer incident list"),
                ("admin", "/incidents", "Admin incident list"),
                ("admin", "/list_users", "Admin user list"),
            ]

            for role, endpoint, label in checks:
                check_response(clients[role].get(endpoint), label)

            print("\nAll sensitive-data checks in this script passed.")

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