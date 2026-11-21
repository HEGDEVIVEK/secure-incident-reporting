# Secure Incident Reporting

A three-tier web application for submitting, reviewing and managing incident
reports, built with security controls aligned to OWASP ASVS and the OWASP Top 10.

| Role | What they can do |
|---|---|
| **User** | Sign in, submit incident reports, view their own reports and the comments on them |
| **Reviewer** | View all incidents, change status (`open`, `under-review`, `closed`), add comments |
| **Admin** | Create accounts, assign roles, activate or deactivate accounts, view all incidents, add comments |

Every key action is written to an append-only audit log.

## Documentation

| File | Contents |
|---|---|
| [`api.md`](api.md) | Every API endpoint: access rules, inputs, responses, errors and audit entries |
| [`MongoDB.md`](MongoDB.md) | Database setup, data model, indexes, least-privilege role and secrets handling |
| `reports/` | SAST results and load and performance test results |

## Architecture

| Tier | Technology | Folder |
|---|---|---|
| Front end | React 19, Vite | `frontend/` |
| Back end | Python 3.12+, FastAPI, Pydantic, PyMongo, Argon2 (`pwdlib`), `keyring` | `backend/` |
| Database | MongoDB Atlas | see `MongoDB.md` |

In development the Vite server proxies `/api/*` to the backend, so the browser only
talks to one origin.

```
.
├── backend/
│   ├── src/
│   │   ├── api.py             # endpoints, error handling, security headers
│   │   ├── schemas.py         # input validation models
│   │   ├── security.py        # Argon2 password hasher
│   │   ├── verifySession.py   # session check used by every protected endpoint
│   │   ├── verifyUser.py      # credential check for login and password change
│   │   └── mongodb.py         # database connection
│   └── tests/                 # automated security and reliability tests
├── frontend/
│   └── src/                   # admin/, reviewers/, users/ dashboards and shared/ components
├── reports/                   # SAST and performance results
├── api.md
└── MongoDB.md
```

## Prerequisites

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- A current Node.js LTS (20.19 or newer) and npm
- A MongoDB Atlas cluster set up as described in [`MongoDB.md`](MongoDB.md)

The project runs on Windows, macOS and Linux. The database password is kept in the
operating system's credential store (Windows Credential Manager, macOS Keychain, or
a Secret Service keyring on Linux).

## Setup

### 1. Database

Follow [`MongoDB.md`](MongoDB.md) to create the database, the unique username index,
the restricted `incident_app` role and the application database user. Create the first
admin account as described there.

### 2. Back end

```
cd backend
uv sync
```

Create `backend/.env` (it is git-ignored):

```
MONGO_HOST=<your-cluster>.mongodb.net
MONGO_USERNAME=<application database user>
MONGO_DB_NAME=secure_incident_reporting
```

Store the database password once in the credential store. It is never written to a file:

```
uv run python -c "import keyring, getpass; keyring.set_password('secure-incident-reporting', 'atlas-db-password', getpass.getpass())"
```

### 3. Front end

```
cd frontend
npm install
```

## Running the application

Start the back end (from `backend/`):

```
uv run python -m uvicorn src.api:app --reload
```

It listens on `http://127.0.0.1:8000`. On success the terminal prints
`MongoDB connected successfully`.

Start the front end (from `frontend/`):

```
npm run dev
```

Open **http://localhost:5173** and sign in. Use `localhost`, not `127.0.0.1` or the
machine's IP address, because the session cookie is marked `Secure` and the
development security policy allows hot reload only for `localhost`.

### Production-style build

The production build serves the stricter Content Security Policy:

```
npm run build
npm run preview
```

Open **http://localhost:4173**. Use this build for security scans and demonstrations.

## Security controls

| Requirement | How it is met |
|---|---|
| SR-1, SR-5 | Every protected endpoint depends on `get_current_user`, which checks the session on each request and re-reads the user, so role changes and deactivation apply immediately |
| SR-2 | Passwords are stored only as Argon2 hashes. New passwords must be 12–128 characters |
| SR-3 | Session cookie is `HttpOnly`, `Secure` and `SameSite=Lax`. Only the SHA-256 hash of the token is stored, and sessions expire after 15 minutes |
| SR-4, SR-6 | Role checks in every handler. Admins cannot change their own role or status |
| SR-7 | Pydantic models reject unknown fields, wrong types and control characters. React escapes all output |
| SR-8 | PyMongo with typed values only. Queries are never built from strings |
| SR-9, SR-10 | Structured logs contain a request ID and route, never passwords, tokens or incident text. Audit entries record user ID, timestamp, action and target ID |
| SR-11, FR-12 | The application's database role can only insert into `audit_logs`, so entries cannot be changed or deleted |
| SR-12, SR-13 | Generic error messages for users, detailed errors in the server log only |
| SR-14 | Database password lives in the OS credential store |
| SR-16 | Security headers on every response, interactive API docs disabled, audit logging for key actions, no sensitive data in responses |

## Testing

### Automated tests

Run from `backend/`, one test at a time, for example:

```
uv run python -m tests.test_authentication
uv run python -m tests.test_role_permissions
uv run python -m tests.test_audit_permissions
```

Most tests call the application in-process and only need the database. They prompt for
the password of a test account, so create dedicated test users first. **Use test data
only, never real personal data.** The load and performance tests
(`test_load`, `test_normal_performance`, `test_write_performance`) send real requests,
so the back end and `npm run dev` must both be running.

| Area | Tests |
|---|---|
| Authentication and sessions | `test_authentication`, `test_logout`, `test_session_validation`, `test_password_change` |
| Authorization | `test_role_permissions`, `test_incident_ownership`, `test_active_role_change`, `test_account_deactivation` |
| Input validation | `test_input_validation`, `test_account_validation`, `test_comment_status_validation` |
| Audit logging and data protection | `test_audit_permissions`, `test_sensitive_data_exposure` |
| Errors and reliability | `test_error_handling`, `test_transaction_rollback`, `test_remaining_rollbacks` |
| Concurrency | `test_concurrent_account_updates`, `test_concurrent_comments`, `test_concurrent_status` |
| Workflow and performance | `test_incident_workflow`, `test_load`, `test_normal_performance`, `test_write_performance` |

### Static analysis (SAST)

```
cd backend
uv run bandit -r src

cd ../frontend
uvx semgrep scan --config auto src
```

Results from the latest runs are saved in `reports/`.

## Notes

- Only synthetic test data is used during development and testing.
- The `.env` file and credentials are never committed.