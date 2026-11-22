from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

# Test 1: Malicious website
response = client.post(
    "/logout",
    headers={"Origin": "https://evil.example"},
)

assert response.status_code == 403
print("PASS: Untrusted origin blocked")


# Test 2: Missing origin
response = client.post("/logout")

assert response.status_code == 403
print("PASS: Missing origin blocked")


# Test 3: Trusted frontend
response = client.post(
    "/logout",
    headers={"Origin": "http://localhost:5173"},
)

assert response.status_code == 200
print("PASS: Trusted origin accepted")