# Secure Incident Reporting — Test Results
 
**Team:** 5  
Pranav Raheja (dol803) 
pranav.raheja@my.utsa.edu 
Frontend development and user interface. 

Vivek Hegde (gvm401) 
vivek.hegde@my.utsa.edu 
Backend development and database implementation. 

Shanmukhanjali Lokam (gpl757) 
shanmukhanjali.lokam@my.utsa.edu 
Application deployment. 
**Updated:** 25 November 2026  

 
The team confirmed that **all 25 test scripts passed in the latest rerun**. Scripts are in `backend/tests/`; reports are in `reports/`; the console output of each test is saved in `reports/test-evidence/` (captured on 22 November 2026, starting at about 18:19 CST according to the log timestamps). The scan and performance figures below retain their original report dates and are not new measurements from that rerun.
 
## 1. Functional, security, and reliability tests
 
All modules below have the prefix `test_` and extension `.py`.
 
| Area | Test modules | Results and requirements |
|---|---|---|
| Authentication and sessions | `authentication`, `logout`, `session_validation`, `password_change` | Authentication enforced; logout/password changes invalidate old sessions; expired/forged tokens rejected. FR-4–5, SR-1–3, SR-5 |
| Accounts and authorization | `role_permissions`, `incident_ownership`, `active_role_change`, `account_deactivation`, `account_validation` | Role/ownership checks, account validation, role changes, deactivation/reactivation, and self-role restrictions passed. FR-1–3, SR-4–7 |
| Incident workflow | `incident_workflow` | Submission, viewing, comments, and status changes passed. FR-6–10 |
| Input validation | `input_validation`, `comment_status_validation` | Invalid types, lengths, IDs, unexpected fields, and injection-style input and and < / > in incident titles and descriptions rejected. SR-7–8 |
| Audit and data protection | `audit_permissions`, `sensitive_data_exposure` | Audit insert allowed; update/delete denied; sensitive-field and secure-storage checks passed. FR-12, SR-2–3, SR-11, SR-16 |
| Errors and rollback | `error_handling`, `transaction_rollback`, `remaining_rollbacks` | Friendly errors, sanitized diagnostic details, recovery, and rollback on audit failure passed. FR-11, NFR-2, NFR-6, SR-9, SR-12–13 |
| Concurrent operations | `concurrent_comments`, `concurrent_status`, `concurrent_account_updates` | Comment, status, and account-update consistency checks passed. NFR-5 |
| CSRF and lockout | `csrf`, `login_lockout` | Missing/untrusted origins blocked; trusted origin accepted; repeated failed logins and password-change attempts throttled. SR-16 |
| Performance | `normal_performance`, `write_performance`, `load` | Sampled normal/write operations within 2 seconds; 50-user login/read workload succeeded. NFR-3–4 |
 
Browser checks also covered role dashboards, refresh/session restoration, and expired-session handling (FR-13, NFR-1).
 
### How to run the tests
 
Run each test from `backend/` as a module, for example:
 
```
uv run python -m tests.test_authentication
uv run python -m tests.test_role_permissions
uv run python -m tests.test_audit_permissions
```
 
- Use dedicated synthetic accounts. Most tests prompt for the password of a test account, and some change passwords, roles, and account status.
- Run the workflow test (`test_incident_workflow`) before tests that reuse its incident.
- Most tests call the application in-process and need only the database. The performance tests (`test_normal_performance`, `test_write_performance`, `test_load`) send real requests, so the backend and `npm run dev` must both be running at `localhost:5173`.
- Requests that change data send a trusted `Origin` header, as the CSRF check requires.
- The login-lockout test leaves its usernames locked until the server restarts or the lockout expires.
- The output file for each test is listed in Section 6.
### How the SAST scans were run
 
```
cd backend
uv run bandit -r src -f txt -o ../reports/backend-sast-bandit-20261122.txt
 
cd ../frontend
uvx semgrep scan --config auto src > ..\reports\frontend-sast-semgrep-20261122.txt 2>&1
```
 
The Semgrep command is for Windows `cmd`. Semgrep scans only files tracked by Git.
 
## 2. Performance
 
Target: `http://localhost:5173`. Times are **milliseconds**, measuring HTTP requests rather than full browser rendering.
 
### Normal load — NFR-3
 
**21 November 2026, 16:31:33 CST.** Five sequential requests per operation. Output: [test_normal_performance.txt](reports/test-evidence/test_normal_performance.txt)
 
| Operation | Median | Maximum | Over 2 seconds |
|---|---:|---:|---:|
| Login | 203 | 222 | 0/5 |
| My incidents | 195 | 214 | 0/5 |
| Logout | 65 | 67 | 0/5 |
 
**PASS:** All sampled operations completed within 2 seconds.
 
### Concurrent load — NFR-4
 
**21 November 2026, 16:35:16 CST.** Fifty virtual users sharing one test account. Output: [test_load.txt](reports/test-evidence/test_load.txt)
 
| Operation | Successful requests | p95 | Maximum |
|---|---:|---:|---:|
| Login | 50/50 HTTP 200 | 2870 | 2874 |
| My incidents | 50/50 HTTP 200 | 645 | 753 |
 
**PASS for this workload.** Login exceeded 2 seconds during the burst; NFR-3 applies to normal load. This was not a sustained mixed-role/write workload.
 
### Write operations — NFR-3
 
**20 November 2026, 20:16:06 CST.** Three sequential workflow runs, 30 operations. Output: [test_write_performance.txt](reports/test-evidence/test_write_performance.txt)
 
| Operation | Median | Maximum | Over 2 seconds |
|---|---:|---:|---:|
| Create incident | 279 | 283 | 0/3 |
| Add comment | 280 | 288 | 0/3 |
| Change incident status | 280 | 291 | 0/6 |
| Create account | 366 | 369 | 0/3 |
| Change account role | 272 | 301 | 0/6 |
| Change password | 444 | 448 | 0/3 |
| Deactivate account | 326 | 344 | 0/3 |
| Reactivate account | 278 | 280 | 0/3 |
 
**PASS:** All writes completed within 2 seconds; highest maximum was **448 ms**.
 
## 3. SAST and DAST
 
| Assessment | Recorded result |
|---|---|
| Backend Bandit | **0 issues** across all severity/confidence levels; 747 lines scanned; 0 files/lines skipped and 0 issues skipped through disabled checks. Started 22 November 2026 at 20:03:13 CST (`2026-11-23 02:03:13.338639+00:00`). |
| Frontend Semgrep | **0 findings, 0 blocking**; Semgrep OSS with `--config auto` ran 200 rules (153 JavaScript, 47 multi-language) on 32 git-tracked files; approximately 100% of lines parsed. Run on 22 November 2026; the output includes no time or commit. Rules that need a Semgrep login were not run, and files not tracked by git were not scanned. |
| ZAP 2.17.0 | ZAP 2.17.0: Report generated on 22 November 2026 at 22:29:46 (timezone unspecified), targeting http://localhost:4173. Results: **0 High**, **0 Medium**, **0 Low**, and **4 Informational** alert types. The previously reported Low XSS alert was not reported in this rerun. |
 
Zero SAST findings means the selected rules detected no issues, not that all vulnerabilities are excluded.
 
**ZAP retest:** The scan report generated on 22 November 2026 at 22:29:46 recorded **0 High, 0 Medium, 0 Low, and 4 Informational alert types**. The previously reported Low XSS alert was not reported in this rerun. Current validation rejects angle brackets in new input, and manual browser checks confirmed existing synthetic payloads displayed without execution.

The remaining informational types are Authentication Request Identified, Modern Web Application, Session Management Response Identified, and User Agent Fuzzer. This HTML report alone does not establish complete authenticated coverage of every endpoint and role; scan configuration/logs and manual test evidence are retained separately.
 
## 4. Selected security evidence
 
The team confirmed these checks. Console output for each automated check is in `reports/test-evidence/`;
 
| Evidence | Result demonstrated | Output |
|---|---|---|
| RBAC | Regular users cannot perform reviewer/admin actions or change their roles; ownership restrictions enforced. SR-4–6 | [test_role_permissions.txt](reports/test-evidence/test_role_permissions.txt), [test_incident_ownership.txt](reports/test-evidence/test_incident_ownership.txt) |
| Cookie flags | `session_token` uses **HttpOnly, Secure, SameSite=Lax**; hide its value in screenshots. SR-3 | [test_logout.txt](reports/test-evidence/test_logout.txt) |
| Session invalidation | Old sessions rejected after logout, password change, or deactivation; reactivation does not revive them. Expired/forged sessions rejected. FR-3, FR-5, SR-1, SR-3, SR-5 | [test_session_validation.txt](reports/test-evidence/test_session_validation.txt), [test_logout.txt](reports/test-evidence/test_logout.txt), [test_password_change.txt](reports/test-evidence/test_password_change.txt), [test_account_deactivation_final.txt](reports/test-evidence/test_account_deactivation_final.txt) |
| Audit restrictions and contents | Insert allowed; update/delete denied. Required events include actor ID, timestamp, action, and target ID, without passwords, tokens, or full descriptions. FR-11–12, SR-9–11 | [test_audit_permissions.txt](reports/test-evidence/test_audit_permissions.txt) |
| CSRF | Missing/untrusted origins return **403**; trusted origin accepted. SR-16 | [test_csrf.txt](reports/test-evidence/test_csrf.txt) |
| Login lockout | Five wrong attempts return **401**; next returns **429 with Retry-After**. Password change also blocked; a different username unaffected under normal capacity. SR-16 | [test_login_lockout.txt](reports/test-evidence/test_login_lockout.txt) |
| XSS | No zero-alert retest is claimed with The latest rerun reported no High, Medium, or Low alerts. Automated tests confirm `<` and `>` in incident titles/descriptions return HTTP 422 and create no incidents. Manual browser checks confirmed existing synthetic payloads displayed without execution. SR-7, SR-16 | [test_input_validation.txt](reports/test-evidence/test_input_validation.txt); [DAST test ](reports/2026-11-22-ZAP-Report-localhost.html) |
 
## 5. Implementation and limitations
 
| Area | Controls/status |
|---|---|
| Authentication | Protected requests reload the active user/role. Argon2 hashes; passwords 12–128 characters; frontend maximum corrected to 128. Sessions expire after 15 minutes; MongoDB stores only token hashes. |
| Input and database access | Pydantic validates inputs and rejects extra fields; text validation rejects unsafe control characters/angle brackets. PyMongo uses structured filters. |
| CSRF and test fixes | Write requests require trusted Origin/Referer (default `http://localhost:5173` and `http://localhost:4173`, configurable with the `TRUSTED_ORIGINS` environment variable); normal tests include the origin. CSRF negative cases remain. Audit-permission tests now fail on unexpected permission or unrelated errors. |
| Login limiter | Each dictionary bounded at **10,000 entries**; full active-lockout capacity temporarily throttles other attempts. Separate isolated checks covered capacity/concurrency; the normal lockout script does not verify capacity or elapsed expiry. State resets on restart and is not shared across processes. |
| Audit and errors | Business changes/audit inserts use transactions. Application audit access is insert-only; privileged DB admins retain access. Friendly errors and sanitized diagnostic records contain request IDs and code locations. |
| Diagnostic-log limitation | Protected on-disk diagnostic logging was **skipped**. Diagnostic-log tamper/access protection is not demonstrated by the separate audit restrictions. |
| Secrets and headers | DB password in OS credential store; credentials excluded from Git. API headers include CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy, Permissions-Policy, and Cache-Control. Local HTTP tests do not prove HTTPS/HSTS enforcement. |
 
`README.md`, `api.md`, and `MongoDB.md` cover major components/setup (NFR-8). The design is modular (NFR-7), testing was on Windows (NFR-9), and test data is synthetic. The PDF has no SR-15.
 
## 6. Evidence files
 
### Scan and performance reports
 
| Report | File |
|---|---|
| Bandit | [backend-sast-bandit-20261122.txt](reports/backend-sast-bandit-20261122.txt) |
| Semgrep | [frontend-sast-semgrep-20261122.txt](reports/frontend-sast-semgrep-20261122.txt) |
| ZAP | [dast-localhost-final.html](reports/2026-11-22-ZAP-Report-localhost.html) |
| Normal load | [test_normal_performance.txt](reports/test-evidence/test_normal_performance.txt) |
| 50-user load | [test_load.txt](reports/test-evidence/test_load.txt) |
| Write operations | [test_write_performance.txt](reports/test-evidence/test_write_performance.txt) |
 
### Test output by area
 
All files are in `reports/test-evidence/`.
 
| Area | Output files |
|---|---|
| Authentication and sessions | [test_authentication.txt](reports/test-evidence/test_authentication.txt), [test_logout.txt](reports/test-evidence/test_logout.txt), [test_session_validation.txt](reports/test-evidence/test_session_validation.txt), [test_password_change.txt](reports/test-evidence/test_password_change.txt) |
| Accounts and authorization | [test_role_permissions.txt](reports/test-evidence/test_role_permissions.txt), [test_incident_ownership.txt](reports/test-evidence/test_incident_ownership.txt), [test_active_role_change.txt](reports/test-evidence/test_active_role_change.txt), [test_account_deactivation_final.txt](reports/test-evidence/test_account_deactivation_final.txt), [test_account_validation_final.txt](reports/test-evidence/test_account_validation_final.txt) |
| Incident workflow | [test_incident_workflow.txt](reports/test-evidence/test_incident_workflow.txt) |
| Input validation | [test_input_validation.txt](reports/test-evidence/test_input_validation.txt), [test_comment_status_validation.txt](reports/test-evidence/test_comment_status_validation.txt) |
| Audit and data protection | [test_audit_permissions.txt](reports/test-evidence/test_audit_permissions.txt), [test_sensitive_data_exposure.txt](reports/test-evidence/test_sensitive_data_exposure.txt) |
| Errors and rollback | [test_error_handling.txt](reports/test-evidence/test_error_handling.txt), [test_transaction_rollback.txt](reports/test-evidence/test_transaction_rollback.txt), [test_remaining_rollbacks.txt](reports/test-evidence/test_remaining_rollbacks.txt) |
| Concurrent operations | [test_concurrent_comments.txt](reports/test-evidence/test_concurrent_comments.txt), [test_concurrent_status.txt](reports/test-evidence/test_concurrent_status.txt), [test_concurrent_account_updates.txt](reports/test-evidence/test_concurrent_account_updates.txt) |
| CSRF and lockout | [test_csrf.txt](reports/test-evidence/test_csrf.txt), [test_login_lockout.txt](reports/test-evidence/test_login_lockout.txt) |
| Performance | [test_normal_performance.txt](reports/test-evidence/test_normal_performance.txt), [test_write_performance.txt](reports/test-evidence/test_write_performance.txt), [test_load.txt](reports/test-evidence/test_load.txt) |
 
 ## 7. Deployment

The application was deployed on **AWS EC2 (Ubuntu)** using Docker Compose (`compose.prod.yaml`) behind a host Nginx reverse proxy with HTTPS enabled.

| Component | Configuration |
|---|---|
| Public URL | `https://secure-incident-report.duckdns.org` (DuckDNS subdomain pointing to EC2) |
| Host reverse proxy | Host Nginx on ports `80` and `443` with a Let's Encrypt TLS certificate (Certbot), forwarding `secure-incident-report.duckdns.org` to `http://127.0.0.1:82` |
| Frontend container | `vivekhegde78/secure-incident-frontend:v1` (multi-stage Node 24 build served via Nginx, mapped `82:80`), proxying `/api/` requests to `http://backend:8000/` over the internal Docker network |
| Backend container | `vivekhegde78/secure-incident-backend:v1` (FastAPI/Uvicorn on port `8000`, not published directly to the host) |
| Secrets and config | `.env` and `mongo_password.txt` excluded from Git and Docker images; mounted at runtime on EC2 (`MONGO_PASSWORD_FILE=/run/secrets/mongo_password`), with `TRUSTED_ORIGINS=https://secure-incident-report.duckdns.org` |
| Database access | MongoDB Atlas over TLS with EC2 IP allowlisted in Atlas Network Access |

- **Verified on deployment:** HTTPS routing, `TRUSTED_ORIGINS` CSRF enforcement, and `HttpOnly; Secure; SameSite=Lax` `session_token` cookie handling over `https://secure-incident-report.duckdns.org`.
