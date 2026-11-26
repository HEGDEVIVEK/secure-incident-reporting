# Secure Incident Reporting – API Reference
 
This document describes every backend endpoint: who may call it, what it expects,
what it returns, and which audit entry it writes. It supports NFR-8 (documentation
of major components). The interactive docs (`/docs`, `/redoc`, `/openapi.json`) are
intentionally disabled (SR-16), so this file is the reference.
 
## Overview
 
| Item | Value |
|---|---|
| Backend | FastAPI, `http://127.0.0.1:8000` |
| From the browser | The Vite server proxies `/api/*` to the backend and removes the `/api` prefix (for example `/api/login` becomes `/login`). |
| Format | JSON request and response bodies |
| Authentication | Session cookie `session_token` (HttpOnly, Secure, SameSite=Lax), valid for 15 minutes |
| Time format | UTC timestamps in ISO 8601 |
| Write requests | `POST`, `PUT`, `PATCH` and `DELETE` must come from a trusted browser origin (see Request origin check) |
| Sign-in protection | Repeated failed sign-ins lock the username for a short time (see Sign-in lockout) |
 
### How authentication works
 
1. `POST /login` checks the credentials, creates a random token and sends it as a cookie.
2. The database stores only the SHA-256 hash of the token, never the token itself.
3. Every protected endpoint reads the cookie, looks up the hash, rejects expired sessions, and re-reads the user from the database. The user must still be active, so role changes and deactivation take effect immediately (SR-1, SR-5).
4. `POST /logout` and `POST /update-password` delete session records, so old cookies stop working.
### Access by role
 
| Endpoint | Public | User | Reviewer | Admin |
|---|:-:|:-:|:-:|:-:|
| `GET /health` | ✔ | ✔ | ✔ | ✔ |
| `POST /login`, `POST /logout`, `POST /update-password` | ✔ | ✔ | ✔ | ✔ |
| `GET /me` | | ✔ | ✔ | ✔ |
| `POST /add_incidents`, `GET /incidents/mine` | | ✔ | | |
| `GET /incidents` | | | ✔ | ✔ |
| `POST /incidents/{id}/comments` | | | ✔ | ✔ |
| `PATCH /incidents/{id}/status` | | | ✔ | |
| `POST /add_users`, `GET /list_users`, `PATCH /users/{id}/status-role` | | | | ✔ |
 
`/update-password` is public because the caller proves identity with the current password.
 
## Common behavior
 
### Error responses
 
Errors use a generic message and never reveal queries, stack traces or internal details (NFR-2, SR-12).
 
| Status | Meaning | Body |
|---|---|---|
| 401 | Not signed in, session expired, or invalid credentials | `{"detail": "Your session has expired. Please sign in again."}` |
| 403 | The role is not allowed, or a write request came from an untrusted origin | `{"detail": "Admin access required"}` (wording varies by endpoint) or `{"detail": "Untrusted request origin"}` |
| 404 | Incident or user not found | `{"detail": "Incident not found"}` / `{"detail": "User not found"}` |
| 409 | Duplicate username | `{"detail": "Username already exists"}` |
| 422 | Invalid input (details are not echoed) | `{"detail": "Invalid input. Please check the submitted fields."}` |
| 429 | Too many failed sign-in attempts for a username | `{"detail": "Too many failed attempts. Please try again later."}` with a `Retry-After` header (seconds) |
| 500 | Unexpected error | `{"detail": "Something went wrong. Please try again.", "request_id": "..."}` |
 
Every response carries an `X-Request-ID` header. The same ID appears in the server log, which holds the detailed error (SR-13).
 
### Security headers (every response, including errors)
 
`Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Strict-Transport-Security`, `Referrer-Policy: no-referrer`, `Permissions-Policy`,
`Cache-Control: no-store`.
 
### Request origin check (CSRF protection, SR-16)
 
Every `POST`, `PUT`, `PATCH` and `DELETE` request must carry an `Origin` header whose value is on the trusted list. If there is no `Origin` header, the `Referer` header is used instead. Otherwise the API answers `403 Untrusted request origin` before doing anything else. Browsers add these headers automatically.
 
- The check applies to every write endpoint, including `/login`, `/logout` and `/update-password`. `GET` requests are not affected.
- The trusted list defaults to `http://localhost:5173` (development server) and `http://localhost:4173` (production-style preview). Set the `TRUSTED_ORIGINS` environment variable, as a comma-separated list, to change it.
- It works together with the `SameSite=Lax` cookie, so another website cannot make a signed-in user's browser change data.
### Sign-in lockout (SR-16)
 
Failed attempts are counted per username (not case-sensitive). `/login` and `/update-password` share one counter, because both check a password.
 
| Setting | Value |
|---|---|
| Failures that trigger a lockout | 5 within 3 minutes |
| Lockout length | 3 minutes |
| Response while locked | `429` with a `Retry-After` header. The password is not checked. |
| Reset | A successful sign-in clears the counter |
| Unknown usernames | Counted the same way, so a lockout does not reveal which accounts exist |
| Storage | In memory. It resets when the server restarts and is not shared between server processes. At most 10,000 usernames are tracked. If 10,000 lockouts are active at once, new attempts are throttled until the earliest one expires. |
 
### Input validation (SR-7)
 
- Unknown fields are rejected, and values must have the exact expected type.
- Incident titles, descriptions and comment text are trimmed. Control characters (other than tab and newline) and the characters `<` and `>` are rejected.
- Passwords for sign-in and password change must be 12 to 128 characters. They are never truncated.
## Endpoints
 
### Public
 
#### `GET /health`
Public status check. Returns `200 {"status": "ok"}`. No sensitive information.
 
#### `POST /login`  (FR-4, SR-1, SR-2, SR-3)
Signs a user in.
 
| Field | Rules |
|---|---|
| `username` | string, 1–64 characters |
| `password` | string, 12–128 characters |
 
- **200:** `{"message": "Signed in", "user": {"id", "role", "username"}}` and the `session_token` cookie.
- **401:** `Invalid username or password`. The same message is used for an unknown user, a wrong password and a deactivated account. A dummy hash is checked for unknown users so timing is similar.
- **422:** invalid input, including a password shorter than 12 characters.
- **429:** the username is locked after repeated failures (see Sign-in lockout).
#### `POST /logout`  (FR-5)
Deletes the session record and clears the cookie. Safe to call when already signed out.
**200:** `{"message": "Signed out"}`.
 
#### `POST /update-password`  (FR-11, SR-2)
Changes a user's own password.
 
| Field | Rules |
|---|---|
| `username` | string, 1–64 characters |
| `current_password` | string, 12–128 characters |
| `new_password` | string, 12–128 characters, must differ from the current password |
 
- **200:** `{"message": "Password updated. Log in with your new password."}`
- **401:** invalid username or current password.
- **422:** invalid input, or new password equals the current one.
- **429:** the username is locked after repeated failures (see Sign-in lockout).
- **Effects:** in one transaction, the hash is replaced (Argon2), all of the user's sessions are deleted, and a `password_changed` audit entry is written. The update only applies if the stored hash is unchanged since it was verified.
### Any signed-in user
 
#### `GET /me`
Returns `{"user": {"id", "username", "role"}}`. Used by the UI to restore the session after a reload. Never cached.

### User only

#### `POST /add_incidents`  (FR-6)
Submits an incident.
 
| Field | Rules |
|---|---|
| `title` | string, 1–200 characters |
| `description` | string, 1–5000 characters |
| `priority` | `high`, `medium` or `low` |
 
- **201:** `{"id": "...", "status": "open"}`
- The submitter is taken from the session, never from the request body. New incidents always start as `open`.
- **Audit:** `incident_created` (stores the title, never the description).
#### `GET /incidents/mine`
Lists the caller's own incidents, newest first. Each item has `id`, `title`, `description`, `priority`, `status`, `created_at` and `comments` (`id`, `text`, `username`, `created_at`). The filter uses the session's user ID, so users cannot see other people's reports.
 
### Reviewer and admin
 
#### `GET /incidents`  (FR-7, FR-10)
Lists every incident regardless of status, newest first. Same fields as `/incidents/mine` plus `submitted_by_name`. The UI filters by status for reviewers. **403** for users.
 
#### `POST /incidents/{incident_id}/comments`  (FR-9)
Adds a comment.
 
| Field | Rules |
|---|---|
| `text` | string, 1–2000 characters |
 
- **201:** `{"id": "...", "incident_id": "..."}`
- **403:** users. **404:** incident not found. **422:** invalid ID or text.
- **Audit:** `comment_created` (stores the incident ID and title, never the comment text).
### Reviewer only
 
#### `PATCH /incidents/{incident_id}/status`  (FR-8)
Changes an incident's status. Admins cannot change status.
 
| Field | Rules |
|---|---|
| `status` | `open`, `under-review` or `closed` |
 
- **200:** `{"id": "...", "status": "..."}`
- **403:** not a reviewer. **404:** incident not found. **422:** invalid ID or status.
- **Audit:** `incident_status_changed` with `old_status` and `new_status`, written only when the status actually changed.
### Admin only
 
#### `POST /add_users`  (FR-1, FR-2)
Creates an account.
 
| Field | Rules |
|---|---|
| `username` | 3–64 characters: lowercase letters, digits and underscore |
| `password` | string, 12–128 characters |
| `role` | `user`, `reviewer` or `admin` (default `user`) |
 
- **201:** `{"id": "...", "username": "..."}`
- **403:** not an admin. **409:** username already exists (enforced by a unique index). **422:** invalid input.
- Only the Argon2 hash of the password is stored.
- **Audit:** `user_created`.
#### `GET /list_users`
Lists all accounts: `[{"id", "username", "role", "is_active"}]`, sorted by username. Password hashes are never read from the database.
 
#### `PATCH /users/{user_id}/status-role`  (FR-2, FR-3, SR-6)
Changes a user's role and/or active status.
 
| Field | Rules |
|---|---|
| `role` | `user`, `reviewer` or `admin` |
| `is_active` | boolean (strict) |
 
- **200:** `{"id", "username", "role", "is_active"}`
- **403:** not an admin, or the admin is changing their own account.
- **404:** user not found. **422:** invalid ID or body.
- Deactivating an account deletes that user's sessions, so access ends immediately.
- **Audit:** `user_account_updated` with the old and new values of whatever changed. No entry is written if nothing changed.
## Audit log (FR-11, FR-12, SR-9, SR-10, SR-11)
 
Every key action writes one entry to `audit_logs` **in the same transaction** as the change, so the change and its record succeed or fail together.
 
Fields common to every entry: `user_id` and `username` (the actor), `action`, `target_type`, `target_id`, `timestamp` (UTC).
 
| Action | Target | Extra fields |
|---|---|---|
| `user_created` | user | `target_username` |
| `user_account_updated` | user | `target_username`, `changes` (old and new role and/or active status) |
| `password_changed` | user | `target_username` |
| `incident_created` | incident | `target_title` |
| `incident_status_changed` | incident | `target_title`, `old_status`, `new_status` |
| `comment_created` | comment | `incident_id`, `incident_title` |
 
- Never stored in logs: passwords, password hashes, session tokens, incident descriptions and comment text.
- No API endpoint reads, changes or deletes audit entries. The database role used by the application is allowed to insert only, so entries are append-only and cannot be altered, even by the application itself.
## Data classification of what the API returns
 
| Level | Examples |
|---|---|
| Public | `/health` status |
| Internal | Incident titles and statuses |
| Sensitive | Incident descriptions, user roles |
| Highly sensitive | Password hashes and session tokens. These are never returned by any endpoint. |
 