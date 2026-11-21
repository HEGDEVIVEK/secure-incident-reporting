import json
from datetime import datetime
from getpass import getpass
from pathlib import Path
from statistics import median
from time import sleep

from test_load import HOST, PORT, request


RUNS = 5
LIMIT_MS = 2000


def main():
    username = input("Regular test username: ").strip()
    password = getpass("Test password: ")

    body = json.dumps({
        "username": username,
        "password": password,
    })

    timings = {
        "Login": [],
        "My incidents": [],
        "Logout": [],
    }

    for number in range(RUNS):
        cookie = ""

        try:
            status, elapsed, cookie = request(
                "POST",
                "/api/login",
                body,
                {"Content-Type": "application/json"},
            )
            assert status == "200", f"Login failed: {status}"
            assert cookie, "Login did not return a cookie"
            timings["Login"].append(elapsed)

            status, elapsed, _ = request(
                "GET",
                "/api/incidents/mine",
                headers={"Cookie": cookie},
            )
            assert status == "200", f"Incident list failed: {status}"
            timings["My incidents"].append(elapsed)

        finally:
            if cookie:
                status, elapsed, _ = request(
                    "POST",
                    "/api/logout",
                    headers={"Cookie": cookie},
                )
                assert status == "200", f"Logout failed: {status}"
                timings["Logout"].append(elapsed)

        print(f"Completed sequential run {number + 1}/{RUNS}")

        if number < RUNS - 1:
            sleep(1)

    now = datetime.now().astimezone()
    lines = [
        f"Normal-load timing | {now.isoformat(timespec='seconds')}",
        f"Target: {HOST}:{PORT} | One request at a time",
        f"Runs per operation: {RUNS}",
    ]

    all_within_limit = True

    for operation, values in timings.items():
        over_limit = sum(value > LIMIT_MS for value in values)
        all_within_limit = all_within_limit and over_limit == 0

        lines.append(
            f"{operation}: median {median(values):.0f} ms, "
            f"max {max(values):.0f} ms, "
            f"over 2 seconds: {over_limit}/{len(values)}"
        )

    lines.append(
        "PASS: All sampled operations completed within 2 seconds."
        if all_within_limit
        else "NEEDS REVIEW: Some sampled operations exceeded 2 seconds."
    )

    report = "\n".join(lines)
    folder = Path(__file__).resolve().parent.parent / "reports"
    folder.mkdir(exist_ok=True)

    output = folder / f"normal-load-{now:%Y%m%d-%H%M%S}.txt"
    output.write_text(report + "\n", encoding="utf-8")

    print("\n" + report)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()