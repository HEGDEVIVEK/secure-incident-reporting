# Change log: branch `ui-and-security-fixes`

These changes are built on top of `main` at commit `1d48589` and split into separate commits, so any one of them can be reviewed or reverted on its own. Each item lists the requirement it serves, for the design document.

Ground rule: **keep everything that already worked.** Existing accounts, endpoints, request and response formats, logging format, and UI flows are unchanged unless listed below.

## Commits

| # | Commit | Requirement | What and why |
|---|---|---|---|
| 1 | Security headers, API docs off | SR-16 | Every API response now carries `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a strict CSP, added inside the existing request middleware. `/docs`, `/redoc`, and `/openapi.json` listed every endpoint publicly; they are now off unless `ENABLE_API_DOCS=true`. |
| 2 | Login lockout | ASVS V2.2.1 | 5 failed password checks for a username within 15 minutes returns HTTP 429 until the window passes, on `/login` and `/update-password`. Stored in a `login_attempts` collection so it works across workers. Unknown usernames behave the same, so it does not reveal which accounts exist. The existing `verify_credentials` call and logging are unchanged; the middleware already logs 401 and 429. |
| 3 | Password policy 12 to 128 | ASVS V2.1.1, V2.1.2 | The old 5 to 15 rule fails both ASVS checks (minimum 12, allow at least 64). New rule applies only where a new password is set; login accepts 1 to 128 so old accounts can still sign in. `test_account_validation.py`: the 16-character rejection case became 11 (too short) and 129 (too long). Frontend inputs and hints updated. |
| 4 | Audit log endpoint and tab | FR-11, FR-12 | `GET /audit-logs` (admin only, read only, newest 200, `no-store`) and an **Audit log** admin tab with action filter and search. Still no API to edit or delete entries. |
| 5 | UI improvements | NFR-1, NFR-6 | Role badge and "Signed in as" in the header; page title; per-status counts that filter on click; Retry buttons restored (they were commented out); fixed "Filter Filter" label; deactivation confirmation; lockout message on login; search box on its own row on phones; system font fallback; unused imports removed (lint clean). |
| 6 | Vite headers and preview proxy | SR-16, NFR-9 | Dev and preview servers send nosniff, frame deny, no-referrer. `npm run preview` now proxies `/api`, so the production build can reach the backend. |
| 7 | Cleanup | NFR-7, NFR-9 | Untracked committed `__pycache__/*.pyc` files (already ignored, committed earlier by mistake). Added `backend/.env.example`. Keyring error message names all three operating systems and shows the setup command. `test_load.py` target configurable by environment variables, defaults unchanged. |
| 8 | Docs | NFR-8 | `README.md`, `docs/ATLAS_SETUP.md`, this file, `frontend/README.md`. |

## Kept as built on `main`

These already existed on `main` and were kept as they are: session restore through `/me`, the `apiFetch` session-expired handler, the reviewer "Return to Open" and "Reopen" buttons, the JSON request logging with request IDs, the 15-minute session, control-character validation, `extra="forbid"` on all schemas, keyring-only credentials, and the full `test_*.py` suite.

## Needs Atlas access (not code)

See `docs/ATLAS_SETUP.md`: the append-only database role (include `login_attempts`), indexes, removing any old `MONGO_URI` line, rotating the shared password, and rerunning the load test with workers.

## Verification

All checks ran against an in-memory MongoDB stand-in, because the Atlas cluster only accepts allow-listed IPs.

- **Team test suite, before and after:** 18 non-performance `test_*.py` scripts were run on `main` and on this branch with seeded test accounts.
  - `main`: 15 pass.
  - This branch: 16 pass. `test_password_change.py` now also passes, because the generated new password is longer than the old 15-character limit allowed.
  - `test_comment_status_validation.py` passes when run after `test_incident_workflow.py`, as it expects.
  - Not checkable here: `test_transaction_rollback.py` (needs real MongoDB transactions) and `test_audit_permissions.py` (needs Atlas's permission system). **Run both against Atlas before merging.**
- **Lockout:** 5 wrong passwords give 401, the 6th gives 429 even with the right password; unknown usernames behave the same; a success clears the counter; `/update-password` locks the same way.
- **Audit log endpoint:** 401 anonymous, 403 user and reviewer, 200 admin; all six FR-11 actions appear; no incident descriptions in the response; `DELETE` returns 405.
- **Headers and docs:** headers present on 200 and 401 responses; `/docs` and `/openapi.json` return 404.
- **Front end:** `npm run lint` clean, `npm run build` succeeds.
- Performance tests (`test_load.py`, `test_normal_performance.py`, `test_write_performance.py`) need the real stack and were not run.
