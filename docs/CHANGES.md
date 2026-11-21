# Change log: branch `ui-redesign`

These changes are built on top of `main` as of 21 November 2026 (after the tests moved into `backend/tests/`) and split into separate commits, so any one of them can be reviewed or reverted on its own. Each item lists the requirement it serves, for the design document.

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
| 7 | Cleanup | NFR-7, NFR-9 | Added `backend/.env.example`. Keyring error message names all three operating systems and shows the setup command. `test_load.py` target configurable by environment variables, defaults unchanged. |
| 8 | Docs | NFR-8 | `README.md`, `docs/ATLAS_SETUP.md`, this file, `frontend/README.md`. |
| 9 | UI redesign and dark mode | NFR-1, NFR-9 | See the next section. No component logic, API calls, or routes changed. |
| 10 | Docs update | NFR-8 | Test commands use the new `backend/tests/` folder (`python -m tests.test_<name>`); code map covers the theme files. |

## UI redesign (commit 9)

The team's deep teal stays the main color (top bar, primary buttons, current page, high priority), with white panels and light grey around it. There are no colored backgrounds on tags or rows. Dark mode is a teal-tinted version of the same roles.

- **Design tokens.** `frontend/src/theme.css` defines every color once with CSS `light-dark()`, plus the base look of inputs, buttons, focus rings, and status tags. Component stylesheets now only handle layout, so a color change happens in one place.
- **Dark mode.** Follows the operating system setting by default. The toggle in the top bar (and on the sign-in screens) saves the choice in `localStorage`. Only the word `light` or `dark` is stored; if storage is blocked, the toggle still works for the visit.
- **Layout.** Slim top bar (name, user, role, theme, log out), and a left navigation rail shared by all three dashboards that turns into a scrollable strip on narrow screens.
- **Incident queue.** One incident per row instead of a three-column card grid, Status is a small circle that fills as the incident moves along (empty for open, half for under review, full for closed), and closed incidents are greyed out. Priority is a three-bar meter (one, two, or three bars). The meta line is short: priority, `#id`, reporter, and time, instead of one string joined with dots. The comments page uses the same meta line.
- **Font.** Atkinson Hyperlegible Next, designed by the Braille Institute for legibility, self-hosted through npm (no requests to outside font servers). Its zero has a slash, so IDs never confuse 0 and O.
- **Small fixes.** New favicon (`index.html` pointed to a deleted file) and a `color-scheme` meta tag.
- **Lockfile.** Only the font's entry was added to `package-lock.json`, by hand, so the file written by the team's npm version is otherwise unchanged.
- **Contrast.** Every text and background pair meets WCAG AA (at least 4.5:1) in both themes. The lowest is grey secondary text on the light background at 5.7:1. Interface marks such as the priority bars meet 3:1.

## Kept as built on `main`

These already existed on `main` and were kept as they are: the `backend/tests/` layout, `test_remaining_rollbacks.py`, session restore through `/me` (staying on the current page after refresh), the `apiFetch` session-expired handler, the reviewer "Return to Open" and "Reopen" buttons, the JSON request logging with request IDs, the 15-minute session, control-character validation, `extra="forbid"` on all schemas, keyring-only credentials, and the full `test_*.py` suite.

## Needs Atlas access (not code)

See `docs/ATLAS_SETUP.md`: the append-only database role (include `login_attempts`), indexes, removing any old `MONGO_URI` line, rotating the shared password, and rerunning the load test with workers.

## Verification

All checks ran against an in-memory MongoDB stand-in, because the Atlas cluster only accepts allow-listed IPs.

- **Team test suite, before and after:** 19 non-performance scripts in `backend/tests/` were run on `main` (21 November) and on this branch with seeded test accounts.
  - `main`: 15 pass.
  - This branch: 16 pass. `test_password_change.py` now also passes, because the generated new password is longer than the old 15-character limit allowed.
  - `test_remaining_rollbacks.py` fails the same way on both ("Account creation was not rolled back"), because the in-memory stand-in has no transactions.
  - `test_comment_status_validation.py` passes when run after `test_incident_workflow.py`, as it expects.
  - Not checkable here: `test_transaction_rollback.py` and `test_remaining_rollbacks.py` (need real MongoDB transactions) and `test_audit_permissions.py` (needs Atlas's permission system). **Run both against Atlas before merging.**
- **Lockout:** 5 wrong passwords give 401, the 6th gives 429 even with the right password; unknown usernames behave the same; a success clears the counter; `/update-password` locks the same way.
- **Audit log endpoint:** 401 anonymous, 403 user and reviewer, 200 admin; all six FR-11 actions appear; no incident descriptions in the response; `DELETE` returns 405.
- **Headers and docs:** headers present on 200 and 401 responses; `/docs` and `/openapi.json` return 404.
- **Front end:** `npm run lint` clean, `npm run build` succeeds, `npm ci` accepts the lockfile.
- **End to end in Chrome**, all three roles, light and dark: 29 checks pass (sign in, refresh keeps the page, report, review, comment, every status change, reopen, create account, deactivation confirm, audit log and its filter, log out, theme toggle and its persistence), with no unexpected console errors.
- Performance tests (`test_load.py`, `test_normal_performance.py`, `test_write_performance.py`) need the real stack and were not run.
