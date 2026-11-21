# MongoDB Atlas Setup and Data Model

This document describes the database used by the Secure Incident Reporting
application: what is stored, how it is protected, and how to set it up again from
scratch. It supports NFR-8 (documentation), FR-12 and SR-11 (append-only audit
logs), SR-8 (safe database access) and SR-14 (secrets handling).

## Environment

| Item | Value |
|---|---|
| Service | MongoDB Atlas (cloud), cluster `Cluster0` |
| Database | `secure_incident_reporting` |
| Collections | `users`, `sessions`, `incidents`, `audit_logs` |
| Connection | `mongodb+srv://` (TLS), `authSource=admin` |
| Why Atlas | The backend uses multi-document transactions, which need a replica set. Atlas provides one. |

## Data model

The data entities required by the project map to collections as follows.

| Required entity | Where it is stored |
|---|---|
| Users | `users` collection |
| Roles | `users.role` field (`user`, `reviewer`, `admin`) |
| Incidents | `incidents` collection |
| Comments | `incidents.comments` (embedded array inside each incident) |
| Audit Logs | `audit_logs` collection |
| (Sessions, extra) | `sessions` collection |

### `users`

| Field | Description |
|---|---|
| `_id` | ObjectId |
| `username` | Unique. 3–64 characters: lowercase letters, digits, underscore |
| `password_hash` | Argon2 hash. The plain password is never stored |
| `role` | `user`, `reviewer` or `admin` |
| `is_active` | `false` means the account is deactivated and cannot sign in |

### `sessions`

| Field | Description |
|---|---|
| `_id` | SHA-256 hash of the session token. The token itself is never stored |
| `user_id`, `username` | Owner of the session |
| `expires_at` | UTC time, 15 minutes after login |

### `incidents`

| Field | Description |
|---|---|
| `_id` | ObjectId |
| `title`, `description`, `priority` | Report content. Priority is `high`, `medium` or `low` |
| `status` | `open`, `under-review` or `closed` |
| `submitted_by_id`, `submitted_by_name` | Taken from the session, never from the request body |
| `created_at` | UTC time |
| `comments[]` | Embedded comments: `_id`, `text`, `user_id`, `username`, `created_at` |

### `audit_logs`

One entry per key action: `user_id`, `username` (the actor), `action`, `target_type`,
`target_id`, `timestamp`, plus action-specific fields. The full list of actions and
fields is in `api.md`. Passwords, hashes, tokens, incident descriptions and comment
text are never written to the audit log.

### Data sensitivity

| Level | Data |
|---|---|
| Internal | Incident titles, statuses |
| Sensitive | Incident descriptions, user roles |
| Highly sensitive | `password_hash`, session token hashes, database credentials |

## Indexes

| Collection | Index | Properties | Purpose |
|---|---|---|---|
| `users` | `_id_` | Unique (default) | Primary key |
| `users` | `username_1` | **Unique** | Prevents duplicate accounts. The API turns a duplicate-key error into a `409 Username already exists` |

The indexes are created once by the database owner in Atlas. The application user
cannot create or drop indexes.

```js
use secure_incident_reporting
db.users.createIndex({ username: 1 }, { unique: true })
```

**Optional cleanup index.** Expired sessions are already rejected by the code, so
this index is not needed for security. It only deletes old session records
automatically:

```js
db.sessions.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })
```

## Least-privilege access (SR-4, SR-11, FR-12)

The application connects as a database user that has **only** one custom role,
`incident_app`. It grants exactly the actions the code needs and nothing more.

| Collection | find | insert | update | remove |
|---|:-:|:-:|:-:|:-:|
| `users` | ✔ | ✔ | ✔ | ✘ |
| `incidents` | ✔ | ✔ | ✔ | ✘ |
| `sessions` | ✔ | ✔ | ✘ | ✔ |
| `audit_logs` | ✘ | ✔ | ✘ | ✘ |

What this means:

- **Audit logs are append-only.** The application can add entries but cannot change,
  delete or even read them. If the application were compromised, an attacker still
  could not erase their tracks (FR-12, SR-11).
- **Nothing can be deleted** except sessions (needed for logout and deactivation).
  Users and incidents are never removed by the application.
- **No administrative commands.** The role cannot create indexes, drop collections,
  manage users or change settings.
- **Privileges add up.** The database user must not have any other role (such as
  `readWrite` or `atlasAdmin`), because that would cancel these restrictions.

`tests/test_audit_permissions.py` checks that update and delete on `audit_logs` are
rejected with the application's credentials.

## Credentials and secrets (SR-14)

| Item | Where it lives |
|---|---|
| `MONGO_HOST`, `MONGO_USERNAME`, `MONGO_DB_NAME` | `backend/.env` (git-ignored) |
| Database password | Operating system credential store (service `secure-incident-reporting`, entry `atlas-db-password`) via the `keyring` library |

No password is stored in a file or in the repository. To save the password once:

```
uv run python -c "import keyring, getpass; keyring.set_password('secure-incident-reporting', 'atlas-db-password', getpass.getpass())"
```

## Setting up from scratch

1. Create an Atlas cluster and a database named `secure_incident_reporting`.
2. Create the `users` unique index shown above (and the optional sessions index).
3. In **Database Access → Custom Roles**, create the role `incident_app` with the
   actions in the table above, each on its collection in `secure_incident_reporting`.
4. In **Database Access → Database Users**, create the application user and assign
   it **only** `incident_app`.
5. In **Network Access**, allow the IP address that runs the backend.
6. Create `backend/.env` and store the password in the credential store (see above).
7. Create the first admin account in the `users` collection (one document with a
   hashed password, `role: "admin"` and `is_active: true`). Further accounts are
   created through the application.

## Reviewing audit logs

The application user cannot read `audit_logs`. The database owner reviews them in
Atlas (**Collections → audit_logs**) or with `mongosh` using the owner's account.
