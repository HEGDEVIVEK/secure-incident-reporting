from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime
from getpass import getpass
from pathlib import Path
from secrets import token_urlsafe
from statistics import median
from time import perf_counter, sleep
from uuid import uuid4

import httpx


BASE_URL = "http://localhost:5173"
RUNS = 3


def main():
    timings = defaultdict(list)
    created_user_ids = []
    clients = {}
    cleanup_warnings = []

    with ExitStack() as stack:

        def new_client():
            return stack.enter_context(
                httpx.Client(base_url=BASE_URL, timeout=30)
            )

        def call(client, method, path, payload=None, expected=200, label=None):
            start = perf_counter()
            response = client.request(method, path, json=payload)
            elapsed = (perf_counter() - start) * 1000

            assert response.status_code == expected, (
                f"{method} {path}: expected HTTP {expected}, "
                f"received HTTP {response.status_code}"
            )

            if label:
                timings[label].append(elapsed)

            return response.json()

        def login(client, username, password, expected_role):
            data = call(
                client,
                "POST",
                "/api/login",
                {"username": username, "password": password},
            )

            # Explicit cookie header for these localhost HTTP timing requests.
            token = client.cookies.get("session_token")
            assert token, "Login did not return a session cookie"
            client.headers["Cookie"] = f"session_token={token}"

            assert data["user"]["role"] == expected_role, (
                f"Use an account with role '{expected_role}'"
            )

        try:
            for role in ("user", "reviewer", "admin"):
                client = new_client()
                clients[role] = client

                print(f"\nEnter credentials for an active {role} account.")
                username = input("Username: ").strip()
                password = getpass("Password: ")
                login(client, username, password, role)

            user = clients["user"]
            reviewer = clients["reviewer"]
            admin = clients["admin"]

            for number in range(RUNS):
                marker = uuid4().hex[:12]

                incident = call(
                    user,
                    "POST",
                    "/api/add_incidents",
                    {
                        "title": f"TEST - Write performance {marker}",
                        "description": "Synthetic performance test.",
                        "priority": "medium",
                    },
                    expected=201,
                    label="Create incident",
                )
                incident_id = incident["id"]

                call(
                    reviewer,
                    "POST",
                    f"/api/incidents/{incident_id}/comments",
                    {"text": f"Performance test comment {marker}"},
                    expected=201,
                    label="Add comment",
                )

                for status in ("under-review", "closed"):
                    call(
                        reviewer,
                        "PATCH",
                        f"/api/incidents/{incident_id}/status",
                        {"status": status},
                        label="Change incident status",
                    )

                test_username = f"perf_{marker}"
                initial_password = token_urlsafe(9)
                new_password = token_urlsafe(9)
                while new_password == initial_password:
                    new_password = token_urlsafe(9)

                account = call(
                    admin,
                    "POST",
                    "/api/add_users",
                    {
                        "username": test_username,
                        "password": initial_password,
                        "role": "user",
                    },
                    expected=201,
                    label="Create account",
                )
                user_id = account["id"]
                created_user_ids.append(user_id)
                account_path = f"/api/users/{user_id}/status-role"

                for role in ("reviewer", "user"):
                    call(
                        admin,
                        "PATCH",
                        account_path,
                        {"role": role, "is_active": True},
                        label="Change account role",
                    )

                test_client = new_client()
                login(test_client, test_username, initial_password, "user")

                try:
                    call(
                        test_client,
                        "POST",
                        "/api/update-password",
                        {
                            "username": test_username,
                            "current_password": initial_password,
                            "new_password": new_password,
                        },
                        label="Change password",
                    )
                finally:
                    call(test_client, "POST", "/api/logout")

                call(
                    admin,
                    "PATCH",
                    account_path,
                    {"role": "user", "is_active": False},
                    label="Deactivate account",
                )

                call(
                    admin,
                    "PATCH",
                    account_path,
                    {"role": "user", "is_active": True},
                    label="Reactivate account",
                )

                print(f"Completed workflow {number + 1}/{RUNS}")
                if number < RUNS - 1:
                    sleep(1)

        finally:
            admin = clients.get("admin")

            if admin:
                for user_id in created_user_ids:
                    try:
                        call(
                            admin,
                            "PATCH",
                            f"/api/users/{user_id}/status-role",
                            {"role": "user", "is_active": False},
                        )
                    except Exception:
                        cleanup_warnings.append(
                            f"Check test account {user_id}: "
                            "could not confirm deactivation."
                        )

            for role, client in clients.items():
                try:
                    call(client, "POST", "/api/logout")
                except Exception:
                    cleanup_warnings.append(
                        f"Could not confirm {role} logout."
                    )

            for warning in cleanup_warnings:
                print(f"Cleanup warning: {warning}")

    now = datetime.now().astimezone()
    lines = [
        f"Write-operation timing | {now.isoformat(timespec='seconds')}",
        f"Target: {BASE_URL}",
        f"Sequential workflow runs: {RUNS}",
    ]

    all_within_limit = True

    for label, values in timings.items():
        over_limit = sum(value > 2000 for value in values)
        all_within_limit = all_within_limit and over_limit == 0

        lines.append(
            f"{label}: median {median(values):.0f} ms, "
            f"max {max(values):.0f} ms, "
            f"over 2 seconds: {over_limit}/{len(values)}"
        )

    lines.append(
        "PASS: All sampled write operations completed within 2 seconds."
        if all_within_limit
        else "NEEDS REVIEW: Some write operations exceeded 2 seconds."
    )
    lines.extend(f"Cleanup warning: {item}" for item in cleanup_warnings)

    report = "\n".join(lines)
    folder = Path(__file__).resolve().parents[2] / "reports"
    folder.mkdir(exist_ok=True)

    output = folder / f"write-performance-{now:%Y%m%d-%H%M%S}.txt"
    output.write_text(report + "\n", encoding="utf-8")

    print("\n" + report)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()