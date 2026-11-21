# Secure Incident Reporting — Test Results

**Team:** [Add team number]  
**Updated:** 21 November 2026  
**Final tested commit / regression date:** [Add before submission]

We tested the application’s functionality, security controls, reliability and performance. This document summarizes our results. Test scripts are in `backend/tests`, and reports are in `reports/`.

## 1. Functional and security tests

All 23 test scripts passed during development. The results below cover those runs and the performance reruns dated 21 November. A complete regression run against the final submission commit remains on our checklist.

| Area | Results | Related requirements |
|---|---|---|
| Accounts and roles | Account creation/validation, role changes, deactivation/reactivation and access checks passed; 14 role-permission checks passed | FR-1–3, SR-4–6 |
| Authentication and sessions | Eight protected-endpoint checks passed; expired/forged tokens rejected; logout and password changes invalidated old sessions; cookie flags checked | FR-4–5, SR-1–3, SR-5 |
| Incident workflow | Submission, ownership, status changes, comments and role-appropriate visibility passed | FR-6–10, SR-4–5 |
| Input and data exposure | Invalid inputs rejected; sensitive-field checks passed; XSS finding reviewed below | SR-2, SR-7, SR-16 |
| Audit logging | Required events/metadata inspected; application account can insert audit records but cannot update/delete them | FR-11–12, SR-9–11 |
| Concurrency and rollback | Concurrent comment/status/account tests passed; tested changes rolled back when audit insertion failed | NFR-5–6, FR-11 |
| Error handling | Friendly 500/422 responses, matching diagnostic reference IDs, secret exclusion and continued operation passed | NFR-2, NFR-6, SR-9, SR-12–13 |
| Browser checks | Role dashboards, refresh/route restoration and expired-session handling worked as expected | FR-13, NFR-1 |

### Running automated tests

Run from `backend/`, one test at a time:

```powershell
uv run python -m tests.test_authentication
uv run python -m tests.test_role_permissions
uv run python -m tests.test_audit_permissions
```

Most tests call the application in-process and need the configured database, without a separately running API server. Interactive tests prompt for test-account credentials. They can modify database records, passwords and sessions: **use dedicated accounts and synthetic data only**. The load and performance tests send network requests, so start the backend and `npm run dev` for their configured localhost:5173 target.

| Area | Test modules in backend/tests |
|---|---|
| Authentication and sessions | `test_authentication`, `test_logout`, `test_session_validation`, `test_password_change` |
| Authorization | `test_role_permissions`, `test_incident_ownership`, `test_active_role_change`, `test_account_deactivation` |
| Input validation | `test_input_validation`, `test_account_validation`, `test_comment_status_validation` |
| Audit logging and data protection | `test_audit_permissions`, `test_sensitive_data_exposure` |
| Errors and reliability | `test_error_handling`, `test_transaction_rollback`, `test_remaining_rollbacks` |
| Concurrency | `test_concurrent_account_updates`, `test_concurrent_comments`, `test_concurrent_status` |
| Workflow and performance | `test_incident_workflow`, `test_load`, `test_normal_performance`, `test_write_performance` |

## 2. Performance

Target: `http://localhost:5173`. Times below are in milliseconds.

### Normal load — NFR-3

Run: **21 November 2026, 16:31:33 CST (UTC−06:00)**. Five runs per operation, with one request at a time.

| Operation | Median (ms) | Maximum (ms) | Requests over 2 seconds |
|---|---:|---:|---:|
| Login | 203 | 222 | 0/5 |
| My incidents | 195 | 214 | 0/5 |
| Logout | 65 | 67 | 0/5 |

**Result: PASS.** All sampled normal-load operations completed within 2 seconds.

### Concurrent load — NFR-4

Run: **21 November 2026, 16:35:16 CST (UTC−06:00)**. Fifty virtual users shared one test account.

| Operation | Successful requests | p95 (ms) | Maximum (ms) |
|---|---:|---:|---:|
| Login | 50/50 HTTP 200 | 2870 | 2874 |
| My incidents | 50/50 HTTP 200 | 645 | 753 |

**Result:** All 50 virtual users successfully logged in and retrieved incidents in this workload. Login exceeded 2 seconds during the concurrent burst; the NFR-3 threshold applies to normal load. This test used one shared account and was not a sustained mixed-workload test. Timings measure HTTP requests, not full browser rendering.

### Write performance

The earlier write test used three workflow runs and 30 operations. All sampled writes completed within 2 seconds; the highest maximum was **448 ms** for password changes. These write timings have not been replaced by the latest login/read/logout runs.

### Evidence

- Normal-load run: `2026-11-21T16:31:33-06:00`.
- Concurrent-load run: `2026-11-21T16:35:16-06:00`.
- [Write-performance report](write-performance-20261120-201606.txt).

Retain the two new run outputs in `reports/` and use their actual saved filenames in the final evidence list. The figures above correspond to these specific runs; they are not averages across the separate load-test attempts.

## 3. SAST and DAST

| Assessment | Recorded result | Evidence |
|---|---|---|
| Backend Bandit | 0 issues | [Bandit report](backend-sast-bandit-current.txt) |
| Frontend Semgrep | 0 findings | [Semgrep report](frontend-sast-semgrep-current.txt) |
| ZAP 2.17.0, localhost:4173 | 0 High, 0 Medium, **1 Low alert type (5 instances)**, 4 Informational alert types | [ZAP report](2026-11-21-ZAP-Report-localhost.html) |
| Manual security testing | Completed checks for privilege escalation, session reuse, ID tampering and XSS handling | Manual testing log and Atlas permission screenshots |

We reran SAST after the security changes and saved the reports in `reports/`. We will associate the final reports with the submission commit. Zero findings means the configured rules detected no issues; it does not guarantee the absence of vulnerabilities.

### Running static analysis

From the project root, using the project’s installed Bandit and Semgrep tooling:

```powershell
cd backend
uv run bandit -r src

cd ../frontend
uvx semgrep scan --config auto src
```

Save the latest scan outputs in `reports/`. These commands run scans; they do not automatically save report files. Record the selected Semgrep rules/configuration with the final results.

### Reviewed Low XSS finding

ZAP found `<script>alert(1);</script>` in JSON returned by `/api/incidents` and `/api/incidents/mine`, involving titles, descriptions or comment text. It assigned Low confidence because the response was not HTML.

We reviewed the affected rendering code. Titles, descriptions and comments use React text expressions, such as `<p>{incident.description}</p>`, without unsafe HTML insertion. We found no executable XSS path in the reviewed rendering code. We retained the Low finding with this explanation rather than changing the scan result to zero findings. No later zero-finding retest is included.

We scoped the submission export to localhost and excluded unrelated Chrome/Google traffic. The original scan recorded 4xx responses and ZAP warnings/errors. These require checking against the scan logs; successful manual logins alone do not establish authenticated active-scan coverage of every endpoint and role.

## 4. Implementation and documentation

### Security controls

We implemented the following controls:

| Requirement | How it is met |
|---|---|
| SR-1, SR-5 | Protected endpoints use `get_current_user` to check the session and re-read the user on each request, so role changes and deactivation take effect immediately |
| SR-2 | Passwords are stored as Argon2 hashes; new passwords must be 12–128 characters |
| SR-3 | Session cookie uses `HttpOnly`, `Secure` and `SameSite=Lax`; only its SHA-256 hash is stored; sessions expire after 15 minutes |
| SR-4, SR-6 | Role checks enforce endpoint access; admins cannot change their own role or status |
| SR-7 | Pydantic validates types and rejects unknown fields; text validation rejects disallowed control characters; affected React fields render user content as escaped text |
| SR-8 | PyMongo queries use structured filters and validated values, rather than concatenated query strings or user-supplied query operators |
| SR-9, SR-10 | Diagnostic logs use request IDs/routes without passwords, tokens or full incident descriptions; audit records include actor ID, timestamp, action and target ID. Audit entries may include incident titles |
| SR-11, FR-12 | The application database role has insert-only access to `audit_logs`; it cannot update or delete entries |
| SR-12, SR-13 | Users receive generic errors; diagnostic details remain in server logs |
| SR-14 | Database password is held in the OS credential store |
| SR-16 | Security headers, disabled interactive API docs, audit logging, and exclusion of password hashes/secrets from API response bodies; authorized users still receive incident data |

We added security headers to API responses, including errors. Frontend document headers require a separate check; our HTTP localhost tests do not establish HTTPS/HSTS enforcement.

Our component and setup documentation supports **NFR-8**:

| Document | Coverage |
|---|---|
| `api.md` | Endpoints, role access, validation, errors and audit events |
| `MongoDB.md` | Data model, unique username index, optional session TTL cleanup, restricted audit role and OS credential-store setup |
| `README.md` | Architecture, prerequisites, setup and run/build instructions |

Atlas audit restrictions apply to the application account; privileged database administrators retain administrative access. We still need to record separate evidence of diagnostic-log protection for SR-11.

We use a modular frontend/backend structure (NFR-7) and ran the tests on Windows (NFR-9). The final review will reconcile endpoint coverage and configuration with this documentation. The requirements PDF does not define SR-15.

### Notes

- Development and testing use synthetic data only, never real personal data.
- We exclude `.env` and credentials from commits.
