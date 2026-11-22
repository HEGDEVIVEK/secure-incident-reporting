# Secure Incident Reporting — Test Results

**Team:** [Add team number]  
**Updated:** 21 November 2026  
**Final tested commit:** [Add Git commit and note any uncommitted changes]

The team confirmed that **all 25 test scripts passed in the latest rerun**. Scripts are in `backend/tests/`; reports are in `reports/`. The scan and performance figures below retain their original report dates and are not new measurements from that rerun.

## 1. Functional, security, and reliability tests

All modules below have the prefix `test_` and extension `.py`.

| Area | Test modules | Results and requirements |
|---|---|---|
| Authentication and sessions | `authentication`, `logout`, `session_validation`, `password_change` | Authentication enforced; logout/password changes invalidate old sessions; expired/forged tokens rejected. FR-4–5, SR-1–3, SR-5 |
| Accounts and authorization | `role_permissions`, `incident_ownership`, `active_role_change`, `account_deactivation`, `account_validation` | Role/ownership checks, account validation, role changes, deactivation/reactivation, and self-role restrictions passed. FR-1–3, SR-4–7 |
| Incident workflow | `incident_workflow` | Submission, viewing, comments, and status changes passed. FR-6–10 |
| Input validation | `input_validation`, `comment_status_validation` | Invalid types, lengths, IDs, unexpected fields, and injection-style input rejected. SR-7–8 |
| Audit and data protection | `audit_permissions`, `sensitive_data_exposure` | Audit insert allowed; update/delete denied; sensitive-field and secure-storage checks passed. FR-12, SR-2–3, SR-11, SR-16 |
| Errors and rollback | `error_handling`, `transaction_rollback`, `remaining_rollbacks` | Friendly errors, sanitized diagnostic details, recovery, and rollback on audit failure passed. FR-11, NFR-2, NFR-6, SR-9, SR-12–13 |
| Concurrent operations | `concurrent_comments`, `concurrent_status`, `concurrent_account_updates` | Comment, status, and account-update consistency checks passed. NFR-5 |
| CSRF and lockout | `csrf`, `login_lockout` | Missing/untrusted origins blocked; trusted origin accepted; repeated failed logins and password-change attempts throttled. SR-16 |
| Performance | `normal_performance`, `write_performance`, `load` | Sampled normal/write operations within 2 seconds; 50-user login/read workload succeeded. NFR-3–4 |

Browser checks also covered role dashboards, refresh/session restoration, and expired-session handling (FR-13, NFR-1).

Run from `backend/`, for example: `uv run python -m tests.test_authentication`. Use dedicated synthetic accounts; some tests change passwords, roles, and account status. Run the workflow test before tests that reuse its incident. Performance tests require the backend and frontend running at `localhost:5173`.

## 2. Performance

Target: `http://localhost:5173`. Times are **milliseconds**, measuring HTTP requests rather than full browser rendering.

### Normal load — NFR-3

**21 November 2026, 16:31:33 CST.** Five sequential requests per operation.

| Operation | Median | Maximum | Over 2 seconds |
|---|---:|---:|---:|
| Login | 203 | 222 | 0/5 |
| My incidents | 195 | 214 | 0/5 |
| Logout | 65 | 67 | 0/5 |

**PASS:** All sampled operations completed within 2 seconds.

### Concurrent load — NFR-4

**21 November 2026, 16:35:16 CST.** Fifty virtual users sharing one test account.

| Operation | Successful requests | p95 | Maximum |
|---|---:|---:|---:|
| Login | 50/50 HTTP 200 | 2870 | 2874 |
| My incidents | 50/50 HTTP 200 | 645 | 753 |

**PASS for this workload.** Login exceeded 2 seconds during the burst; NFR-3 applies to normal load. This was not a sustained mixed-role/write workload.

### Write operations — NFR-3

**20 November 2026, 20:16:06 CST.** Three sequential workflow runs, 30 operations.

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
| Backend Bandit | **0 issues** across all severity/confidence levels; 734 lines scanned; 0 files/lines skipped and 0 issues skipped through disabled checks. Started 21 November 2026 at 19:36:43 CST (`2026-11-22 01:36:43.974604+00:00`). |
| Frontend Semgrep | **0 findings, 0 blocking**; 68 JavaScript rules executed on 18 files; approximately 100% of lines parsed. Initial status listed 28 files/74 rules. Scan completed; timestamp/commit not included in the supplied output. |
| ZAP 2.17.0 | **0 High, 0 Medium, 1 Low alert type (5 instances), 4 Informational types**. Target: `http://localhost:4173`. Report generated 21 November 2026 at 14:53:34; timezone unspecified. |

Zero SAST findings means the selected rules detected no issues, not that all vulnerabilities are excluded.

**ZAP Low finding:** Script payloads appeared in JSON from `/api/incidents` and `/api/incidents/mine` in titles, descriptions, or comments. ZAP assigned Low confidence because the response was not HTML. Reviewed components render these values as escaped React text; the team reports manual XSS checks completed. Current validation rejects angle brackets in new input but does not remove existing test payloads. The finding remains documented; no zero-alert retest is claimed.

Informational types: Authentication Request Identified, Modern Web Application, Session Management Response Identified, and User Agent Fuzzer. Full authenticated coverage of every endpoint/role is not established by this HTML report alone; retain scan configuration/logs to explain coverage and earlier 4xx responses or scan warnings.

## 4. Selected security evidence

The team confirmed these checks. Keep selected screenshots/output in `reports/test-evidence/` and list their actual filenames; separate output files for every test are optional.

| Evidence | Result demonstrated |
|---|---|
| RBAC | Regular users cannot perform reviewer/admin actions or change their roles; ownership restrictions enforced. SR-4–6 |
| Cookie flags | `session_token` uses **HttpOnly, Secure, SameSite=Lax**; hide its value in screenshots. SR-3 |
| Session invalidation | Old sessions rejected after logout, password change, or deactivation; reactivation does not revive them. Expired/forged sessions rejected. FR-3, FR-5, SR-1, SR-3, SR-5 |
| Audit restrictions and contents | Insert allowed; update/delete denied. Required events include actor ID, timestamp, action, and target ID, without passwords, tokens, or full descriptions. FR-11–12, SR-9–11 |
| CSRF | Missing/untrusted origins return **403**; trusted origin accepted. SR-16 |
| Login lockout | Five wrong attempts return **401**; next returns **429 with Retry-After**. Password change also blocked; a different username unaffected under normal capacity. SR-16 |
| XSS | New invalid payload rejected; existing synthetic payload displayed without execution. SR-7, SR-16 |

Shared console output directly supports audit-permission and login-lockout results. The full rerun/manual-check status is team-confirmed; screenshot filenames were not supplied for this update.

## 5. Implementation and limitations

| Area | Controls/status |
|---|---|
| Authentication | Protected requests reload the active user/role. Argon2 hashes; passwords 12–128 characters; frontend maximum corrected to 128. Sessions expire after 15 minutes; MongoDB stores only token hashes. |
| Input and database access | Pydantic validates inputs and rejects extra fields; text validation rejects unsafe control characters/angle brackets. PyMongo uses structured filters. |
| CSRF and test fixes | Write requests require trusted Origin/Referer; normal tests include the origin. CSRF negative cases remain. Audit-permission tests now fail on unexpected permission or unrelated errors. |
| Login limiter | Each dictionary bounded at **10,000 entries**; full active-lockout capacity temporarily throttles other attempts. Separate isolated checks covered capacity/concurrency; the normal lockout script does not verify capacity or elapsed expiry. State resets on restart and is not shared across processes. |
| Audit and errors | Business changes/audit inserts use transactions. Application audit access is insert-only; privileged DB admins retain access. Friendly errors and sanitized diagnostic records contain request IDs and code locations. |
| Diagnostic-log limitation | Protected on-disk diagnostic logging was **skipped**. Diagnostic-log tamper/access protection is not demonstrated by the separate audit restrictions. |
| Secrets and headers | DB password in OS credential store; credentials excluded from Git. API headers include CSP, X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy, Permissions-Policy, and Cache-Control. Local HTTP tests do not prove HTTPS/HSTS enforcement. |

`README.md`, `api.md`, and `MongoDB.md` cover major components/setup (NFR-8). The design is modular (NFR-7), testing was on Windows (NFR-9), and test data is synthetic. The PDF has no SR-15.

## 6. Evidence files

These filenames were present in the reviewed ZIP. Update links if newer final reports replace them.

| Report | File |
|---|---|
| Bandit | [backend-sast-bandit-20261121.txt](reports/backend-sast-bandit-20261121.txt) |
| Semgrep | [frontend-sast-semgrep-current.txt](reports/frontend-sast-semgrep-current.txt) |
| ZAP | [dast-localhost-final.html](reports/dast-localhost-final.html) |
| Normal load | [normal-load-20261121-163133.txt](reports/normal-load-20261121-163133.txt) |
| 50-user load | [nfr4-load-20261121-163516.txt](reports/nfr4-load-20261121-163516.txt) |
| Write operations | [write-performance-20261120-201606.txt](reports/write-performance-20261120-201606.txt) |
| Selected security evidence | `reports/test-evidence/` — add actual filenames |

**Before submission:** Fill in team number/commit, confirm evidence links and the source revision covered by each report, and retain the ZAP Low finding and diagnostic-log limitation.
