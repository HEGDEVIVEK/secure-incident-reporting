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