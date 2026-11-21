# Secure Incident Reporting

A three-tier web application where **users** submit incident reports, **reviewers** comment on them and move them through open, under review, and closed, and **administrators** manage accounts and read the audit trail. Built for the CS 5343 final project with security controls aligned to OWASP ASVS Level 1/2 and the OWASP Top 10.

| Tier | Technology | Folder |
|---|---|---|
| Front end | React 19, React Router, Vite | `frontend/` |
| Backend | Python 3.12+, FastAPI, Pydantic, pwdlib (Argon2) | `backend/` |
| Database | MongoDB Atlas (replica set, needed for transactions) | external |

---

## 1. How it fits together

```
Browser ──► Vite server (:5173) ──/api/*──► FastAPI (:8000) ──► MongoDB Atlas
            serves the React app            authN, RBAC,        users, incidents,
            adds security headers           validation,         sessions, audit_logs,
                                            logging             login_attempts
```

- The browser talks to one origin only. Vite forwards `/api/*` to FastAPI, so the session cookie stays first-party.
- The session cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, and lasts 15 minutes. The browser holds a random token; MongoDB stores only its SHA-256 hash.
- Every key action writes its audit entry **in the same MongoDB transaction** as the change, so an action cannot succeed without being logged.

## 2. Code map

### Backend (`backend/src/`)

| File | Responsibility |
|---|---|
| `api.py` | All endpoints; request middleware (request IDs, error handling, logging, security headers); role checks |
| `schemas.py` | Pydantic request models: lengths, allowed values, control-character checks, unknown fields rejected |
| `verifySession.py` | `get_current_user`: turns the session cookie into the signed-in, active user |
| `verifyUser.py` | Password check with Argon2, with equal work for unknown usernames |
| `loginLimiter.py` | Lockout after 5 failed password checks in 15 minutes per username |
| `security.py` | The Argon2 password hasher |
| `mongodb.py` | Database connection; password read from the OS credential store (keyring) |

Tests live in `backend/tests/` (see section 8).

### Front end (`frontend/src/`)

| Folder | Contents |
|---|---|
| `theme.css` | Design tokens (every color defined once for light and dark), base styles for controls, buttons, focus rings, status tags |
| `App.jsx`, `App.css` | Restores the session on page load (`/me`), top bar, navigation rail shared by all dashboards, picks the dashboard by role |
| `shared/ThemeToggle.jsx`, `shared/theme.js` | Light and dark mode: follows the system setting until the user chooses, then remembers the choice |
| `shared/api.js` | `apiFetch`: sends any 401 to one "session expired" handler |
| `shared/` | Login, change password, incident list (cards, search, filters, status summary), incident discussion (comments and status) |
| `users/` | Report an incident, My incidents |
| `reviewers/` | All incidents, Comments and status |
| `admin/` | Create account, All incidents, Comments, Update role and status, Audit log |

The UI hides actions a role cannot use, but **the backend enforces every rule on every request**. The UI is never trusted.

## 3. Roles and permissions

| Action | User | Reviewer | Admin |
|---|:-:|:-:|:-:|
| Submit an incident, see own incidents | ✅ | ✅ | ✅ |
| See all incidents | | ✅ | ✅ |
| Comment on incidents | | ✅ | ✅ |
| Change incident status (open, under-review, closed) | | ✅ | |
| Create accounts, change role or active status of **other** accounts | | | ✅ |
| Read the audit log | | | ✅ |
| Change own role or status | ❌ | ❌ | ❌ |

## 4. API endpoints

| Method and path | Who | Purpose |
|---|---|---|
| `GET /health` | public | Liveness check |
| `POST /login` | public | Sign in, sets the session cookie |
| `POST /logout` | public | Deletes the server session and the cookie |
| `POST /update-password` | public (needs current password) | Change password, ends all sessions |
| `GET /me` | signed in | Who is signed in (used after a page refresh) |
| `POST /add_users` | admin | Create an account with a role |
| `GET /list_users` | admin | List accounts (no password hashes) |
| `PATCH /users/{id}/status-role` | admin | Change role or active status of another account |
| `GET /audit-logs` | admin | Newest 200 audit entries (read only) |
| `POST /add_incidents` | signed in | Submit an incident |
| `GET /incidents/mine` | signed in | Own incidents with comments |
| `GET /incidents` | reviewer, admin | All incidents with comments |
| `POST /incidents/{id}/comments` | reviewer, admin | Add a comment |
| `PATCH /incidents/{id}/status` | reviewer | Change status |

Interactive API docs (`/docs`) are **off by default**. Set `ENABLE_API_DOCS=true` in `.env` only on your own machine.

## 5. Setup

Works on Windows, macOS, and Linux.

### Prerequisites

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- Node.js 22.22 or newer (required by React Router 8)
- Access to the team's MongoDB Atlas cluster, with your IP added under **Network Access**

### Backend

```bash
cd backend
uv sync
cp .env.example .env         # Windows: copy .env.example .env
```

Fill in `MONGO_HOST`, `MONGO_USERNAME`, and `MONGO_DB_NAME` in `.env`. Then store the database password in your operating system's credential store (Windows Credential Manager, macOS Keychain, or Linux Secret Service). It is never written to a file (SR-14):

```bash
uv run python -c "import keyring, getpass; keyring.set_password('secure-incident-reporting', 'atlas-db-password', getpass.getpass())"
```

Run it:

```bash
uv run uvicorn src.api:app --port 8000 --workers 4
```

### Front end

```bash
cd frontend
npm ci
npm run dev                  # http://localhost:5173
```

For a production build: `npm run build && npm run preview` (http://localhost:4173, same `/api` proxy).

Use Chrome, Edge, or Firefox. The session cookie is marked `Secure`; these browsers accept it on `http://localhost` during development.

### Database setup (one time, in Atlas)

See [`docs/ATLAS_SETUP.md`](docs/ATLAS_SETUP.md): the least-privilege database role that makes audit logs append-only, and the indexes the app expects.

## 6. Security controls

| Requirement | How it is met | Where |
|---|---|---|
| SR-1 authentication on non-public endpoints | `Depends(get_current_user)` on every non-public route | `api.py`, `verifySession.py` |
| SR-2 password storage | Argon2 via `pwdlib` | `security.py` |
| SR-3 cookie flags | `HttpOnly`, `Secure`, `SameSite=Lax`, 15-minute lifetime | `api.py` login |
| SR-4, SR-5 RBAC on every request | Role read fresh from the database on every request, then checked in each endpoint | `verifySession.py`, `api.py` |
| SR-6 no self role change | Admin update rejects the admin's own ID; UI marks own row "Protected" | `api.py`, `AccountStatusRole.jsx` |
| SR-7 input validation | Pydantic models with lengths, regex, enums, control-character checks, `extra="forbid"`; ObjectId checks | `schemas.py`, `api.py` |
| SR-8 parameterized queries | PyMongo builds queries as documents; input is never joined into query strings; type checks block operator injection like `{"$ne": null}` | `api.py`, `schemas.py` |
| SR-9 no sensitive data in logs | Audit entries store titles and IDs, never descriptions, passwords, or tokens. App logs record the route template, status, and a request ID only: no URLs, no bodies, no exception messages | `api.py` |
| SR-10 audit fields | Every entry has `user_id`, `timestamp`, `action`, `target_id` | `api.py` |
| SR-11, FR-12 tamper protection | No API to edit or delete audit entries; the app's DB user can only insert and read `audit_logs` (checked by `tests/test_audit_permissions.py`) | `docs/ATLAS_SETUP.md` |
| SR-12, NFR-2 safe error messages | Generic messages for validation errors, failed logins, and unexpected errors, with a reference ID | `api.py` |
| SR-13 detailed errors logged | Unexpected errors log exception type and code locations (file, line, function) with the same request ID the user sees | `api.py` middleware |
| SR-14 secrets | DB password in the OS credential store via keyring | `mongodb.py` |
| SR-16 misconfiguration | API docs off, security headers on API and front end, `.env` git-ignored | `api.py`, `vite.config.js` |
| ASVS V2.1 password policy | New passwords 12 to 128 characters; older accounts can still sign in and change theirs | `schemas.py` |
| ASVS V2.2 brute force | Lockout after 5 failures in 15 minutes, same for unknown usernames | `loginLimiter.py` |
| NFR-5 integrity | Each change and its audit entry share one transaction; password change re-checks the old hash inside the transaction | `api.py` |

## 7. Logging

There are two separate records:

1. **Audit trail** (`audit_logs` collection) for FR-11: incident created, status changed, comment added, user created, role or active status changed, password changed. Admins see it in the **Audit log** tab.
2. **Application log** (JSON lines on standard output) for monitoring and diagnosis: every rejected request (401, 403, 404, 429), validation failures (error count only), and unexpected errors (exception type and code locations). Each line carries a request ID that also appears in the `X-Request-ID` response header, so a user's error reference can be matched to the log line. In production, the process manager (for example systemd's journal) keeps these logs.

## 8. Testing

| What | How | Notes |
|---|---|---|
| Security and functional tests | `cd backend && uv run python -m tests.test_<name>` | Most ask for test account credentials. They use the real database, so use test accounts and synthetic data only. |
| Audit log tamper check (FR-12) | `uv run python -m tests.test_audit_permissions` | Update and delete must be blocked |
| Transaction rollback (NFR-5) | `uv run python -m tests.test_transaction_rollback` and `tests.test_remaining_rollbacks` | Needs the real database (transactions) |
| Load, NFR-3 and NFR-4 | `uv run python -m tests.test_load` (through Vite) or `LOAD_TEST_PORT=8000 LOAD_TEST_PREFIX= uv run python -m tests.test_load` (backend only) | Report saved in `reports/` |
| Other performance | `tests.test_normal_performance`, `tests.test_write_performance` | Reports in `reports/` |
| SAST, backend | `bandit -r backend/src` | `reports/` |
| SAST, front end | `semgrep scan --config auto frontend` | `reports/` |
| Lint and dependencies, front end | `cd frontend && npm run lint && npm audit` | console |

## 9. Known limitations

- Incident lists are not paginated. That is fine for the project's scale (50 concurrent users) but would need paging for large data sets.
- Anyone who knows a username can trigger its lockout, blocking that account for 15 minutes. This is the usual tradeoff of account lockout.
- Atlas project owners can still change data from the Atlas console. The append-only guarantee applies to the application's database user.
- Argon2 is deliberately slow. A burst of 50 simultaneous logins is the slowest operation; run the backend with several workers.
