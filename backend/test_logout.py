from getpass import getpass
from http.cookies import SimpleCookie

from fastapi.testclient import TestClient

from src.api import app

username = input("Active test account username: ").strip()
password = getpass("Password: ")

with TestClient(app, base_url="https://testserver") as client:
    token = None

    try:
        login = client.post("/login", json={
            "username": username,
            "password": password,
        })

        assert login.status_code == 200, (
            f"Login failed: HTTP {login.status_code}"
        )

        token = client.cookies.get("session_token")
        assert token, "Login did not provide a session cookie"

        before_logout = client.get("/incidents/mine")
        assert before_logout.status_code == 200
        print("PASS: Session allows access before logout")

        cookies = SimpleCookie()
        cookies.load(login.headers["set-cookie"])
        session_cookie = cookies["session_token"]

        assert session_cookie["httponly"], "HttpOnly flag missing"
        assert session_cookie["secure"], "Secure flag missing"
        assert session_cookie["samesite"].lower() in ("lax", "strict")
        print("PASS: Session cookie has HttpOnly, Secure, and SameSite flags")

        logout = client.post("/logout")

        assert logout.status_code == 200
        assert client.cookies.get("session_token") is None
        print("PASS: Logout succeeds and removes the client cookie")

        # Attempt to reuse the original token after logout.
        replay = client.get(
            "/incidents/mine",
            headers={"Cookie": f"session_token={token}"},
        )

        assert replay.status_code == 401, (
            f"Old session token was not rejected: HTTP {replay.status_code}"
        )
        print("PASS: Reusing the logged-out session token returns HTTP 401")

        print("\nAll logout checks passed.")

    finally:
        # Clean up this test session even if an earlier check fails.
        if token:
            client.post(
                "/logout",
                headers={"Cookie": f"session_token={token}"},
            )