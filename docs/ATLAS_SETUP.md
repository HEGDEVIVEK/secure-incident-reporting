# MongoDB Atlas setup

One-time steps, done by whoever owns the Atlas project. Nothing here changes application code. All steps are in the Atlas web UI.

## Step 1. Check what the app's database user can do today

In Atlas: **Security > Database Access**, find the user in the app's connection string (for example `teammate_dev`) and look at its role.

- If it says `readWrite`, `readWriteAnyDatabase`, `dbAdmin`, or `atlasAdmin`, the app (or anyone holding that password) can **delete or edit audit logs**. FR-12 and SR-11 are not enforced yet. Do step 2.
- If it already has a custom role like the one below, skip to step 3.

## Step 2. Least-privilege role: audit logs become append-only (FR-12, SR-11)

**Security > Database Access > Custom Roles > Add New Custom Role**, name it `incident_app`, and add these actions. Database = your `MONGO_DB_NAME`, one row per collection:

| Collection | Actions to allow |
|---|---|
| `users` | `find`, `insert`, `update` |
| `incidents` | `find`, `insert`, `update` |
| `sessions` | `find`, `insert`, `remove` |
| `login_attempts` | `find`, `insert`, `remove` |
| `audit_logs` | `find`, `insert` **(nothing else)** |

These are exactly the operations the code uses (checked against every query in `backend/src/`). Then edit the app's database user and give it **only** `incident_app`.

Keep a separate admin database user for maintenance, and never put its password in the app.

**How to prove it works (good for the demo video):** connect as the app user (mongosh or Compass) and run

```js
db.audit_logs.deleteOne({})
db.audit_logs.updateOne({}, { $set: { action: "tampered" } })
```

Both should fail with `not authorized`. Then `db.audit_logs.find().limit(1)` should still work.

The same check is automated: run `uv run python test_audit_permissions.py` in `backend/`. It should print `PASS` for insert, and `PASS ... blocked` for both update and delete.

## Step 3. Indexes

**Database > Browse Collections > (collection) > Indexes > Create Index**:

| Collection | Index | Options | Why |
|---|---|---|---|
| `users` | `{ "username": 1 }` | `{ "unique": true }` | Duplicate usernames return 409. Probably exists already; check. |
| `sessions` | `{ "expires_at": 1 }` | `{ "expireAfterSeconds": 0 }` | MongoDB deletes expired sessions automatically |
| `login_attempts` | `{ "created_at": 1 }` | `{ "expireAfterSeconds": 900 }` | Old failed-login records clean themselves up after 15 minutes |
| `login_attempts` | `{ "username": 1 }` | none | Fast lockout check |

The app works without the TTL indexes (it checks expiry itself); they only keep the collections small.

## Step 4. Password in the OS credential store (SR-14)

`mongodb.py` already reads the password from keyring. On each machine, make sure:

1. The password is stored once:
   ```bash
   cd backend
   uv run python -c "import keyring, getpass; keyring.set_password('secure-incident-reporting', 'atlas-db-password', getpass.getpass())"
   ```
2. `.env` has only `MONGO_HOST`, `MONGO_USERNAME`, and `MONGO_DB_NAME`. If an old `MONGO_URI=...` line with the password is still there, **delete it**: the code no longer uses it, and it is a plaintext copy of the secret.

## Step 5. Rotate the shared password

The app user's password was shared in chat messages, so treat it as exposed. After step 4 works, change it under **Database Access > Edit > Edit Password**, and everyone runs the keyring command in step 4 again with the new one.

## Step 6. Rerun the load test (NFR-3, NFR-4)

The latest report (`reports/nfr4-load-20261120-184424.txt`) has login p95 at about 4.5 s, above the 2 s target. It was measured through the Vite dev server, most likely with a single backend process. Run the backend with workers and test it directly:

```bash
cd backend
uv run uvicorn src.api:app --port 8000 --workers 4
# in another terminal:
LOAD_TEST_PORT=8000 LOAD_TEST_PREFIX= uv run python test_load.py
```

Windows PowerShell: `$env:LOAD_TEST_PORT="8000"; $env:LOAD_TEST_PREFIX=""; uv run python test_load.py`

A new report appears in `reports/`.
