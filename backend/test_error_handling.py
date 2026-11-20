import io
import json
import logging
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api import app, logger

captured_logs = io.StringIO()
capture_handler = logging.StreamHandler(captured_logs)
logger.addHandler(capture_handler)

secret_marker = "DUMMY_SECRET_FOR_TEST_ONLY"
test_password = "TestPassword123"

try:
    with TestClient(app) as client:
        # Simulate a failure before login can create a database session.
        with patch(
            "src.api.verify_credentials",
            side_effect=RuntimeError(secret_marker),
        ):
            response = client.post(
                "/login",
                json={
                    "username": "error_test_user",
                    "password": test_password,
                },
            )

        assert response.status_code == 500, "Expected HTTP 500"
        body = response.json()
        assert body["detail"] == "Something went wrong. Please try again."
        print("PASS: Unexpected error returns a friendly HTTP 500 response")

        request_id = body["request_id"]
        assert request_id and request_id == response.headers["X-Request-ID"]

        log_text = captured_logs.getvalue()
        records = [json.loads(line) for line in log_text.splitlines()]
        entry = next(
            item for item in records
            if item.get("event") == "unexpected_error"
            and item.get("request_id") == request_id
        )
        assert entry["exception_type"] == "RuntimeError"
        assert entry["frames"] and entry["timestamp"]
        assert entry["route"] == "/login"
        print("PASS: Diagnostic log and response have matching reference IDs")

        for value in (secret_marker, test_password):
            assert value not in response.text, "Sensitive value in response"
            assert value not in log_text, "Sensitive value in application log"
        print("PASS: Test secrets are absent from response and application log")

        invalid = client.post("/login", json={})
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == (
            "Invalid input. Please check the submitted fields."
        )
        print("PASS: Invalid input still returns a friendly HTTP 422 response")

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        print("PASS: Application responds successfully after the error")

        print("Error reference:", request_id)
        print("All error-handling checks passed.")

finally:
    logger.removeHandler(capture_handler)
    capture_handler.close()