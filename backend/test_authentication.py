from bson import ObjectId
from fastapi.testclient import TestClient

from src.api import app

# Fresh IDs ensure test requests do not target existing records.
test_id = str(ObjectId())

cases = [
    ("GET", "/list_users", None),
    ("GET", "/incidents", None),
    ("GET", "/incidents/mine", None),

    ("POST", "/add_users", {
        "username": f"auth_check_{test_id}",
        "password": "TestPassword123",
        "role": "user",
    }),

    ("POST", "/add_incidents", {
        "title": "Authentication test",
        "description": "Synthetic test data",
        "priority": "low",
    }),

    ("PATCH", f"/users/{test_id}/status-role", {
        "role": "user",
        "is_active": True,
    }),

    ("POST", f"/incidents/{test_id}/comments", {
        "text": "Synthetic test comment",
    }),

    ("PATCH", f"/incidents/{test_id}/status", {
        "status": "closed",
    }),
]

with TestClient(app, base_url="https://testserver") as client:
    for method, path, payload in cases:
        client.cookies.clear()
        options = {"json": payload} if payload is not None else {}

        response = client.request(method, path, **options)

        assert response.status_code == 401, (
            f"FAIL: {method} {path} — "
            f"expected 401, received {response.status_code}"
        )

        assert response.json()["detail"] == "Please sign in", (
            f"FAIL: Unexpected authentication message for {method} {path}"
        )

        print(f"PASS: {method} {path} rejects an unauthenticated request")

print(f"All {len(cases)} session-protected endpoint checks passed.")