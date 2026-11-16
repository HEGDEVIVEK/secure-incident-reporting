import http.client
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from getpass import getpass
from http.cookies import SimpleCookie
from pathlib import Path
from threading import Barrier
from time import perf_counter

USERS = 50
HOST = "localhost"
PORT = 5173


def request(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    start = perf_counter()
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        response.read()
        cookies = SimpleCookie()
        for value in response.headers.get_all("Set-Cookie", []):
            cookies.load(value)
        cookie = "; ".join(f"{c.key}={c.coded_value}" for c in cookies.values())
        status = str(response.status)
    except (OSError, http.client.HTTPException) as error:
        status = type(error).__name__
        cookie = ""
    finally:
        conn.close()
    return status, (perf_counter() - start) * 1000, cookie


def summarize(label, results):
    counts = Counter(status for status, _ in results)
    times = sorted(ms for status, ms in results if status == "200")
    line = f"{label}: {len(times)}/{USERS} returned 200 | outcomes: {dict(counts)}"
    if times:
        p95 = times[math.ceil(0.95 * len(times)) - 1]
        line += f" | successful requests: p95 {p95:.0f} ms, max {max(times):.0f} ms"
    return line


def main():
    username = input("Regular test username: ")
    password = getpass("Test password: ")
    body = json.dumps({"username": username, "password": password})
    gate = Barrier(USERS)

    def virtual_user(_):
        gate.wait()
        status, ms, cookie = request(
            "POST", "/api/login", body, {"Content-Type": "application/json"}
        )
        login = (status, ms)
        gate.wait()
        if status != "200" or not cookie:
            return login, ("skipped: no successful login with cookie", 0)
        status, ms, _ = request("GET", "/api/incidents/mine", headers={"Cookie": cookie})
        return login, (status, ms)

    with ThreadPoolExecutor(max_workers=USERS) as pool:
        results = list(pool.map(virtual_user, range(USERS)))

    logins, reads = zip(*results)
    now = datetime.now().astimezone()
    report = "\n".join([
        f"NFR-4 load test | {now.isoformat(timespec='seconds')}",
        f"Target: {HOST}:{PORT} | 50 virtual users sharing one test account",
        summarize("Login", logins),
        summarize("My incidents", reads),
    ])
    folder = Path(__file__).resolve().parent.parent / "reports"
    folder.mkdir(exist_ok=True)
    output = folder / f"nfr4-load-{now:%Y%m%d-%H%M%S}.txt"
    output.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()