# Secure Desk - Demo Guide

This guide reproduces the complete Secure Desk demonstration locally.
It uses two isolated Docker containers:

- vulnerable baseline: `http://127.0.0.1:5051`
- corrected application: `http://127.0.0.1:5050`

Only test these attacks against this local application.

## 1. Before the demonstration

Open PowerShell in the repository:

```powershell
Set-Location C:\Users\alhab\Desktop\9raya\Devsecops
git status --short
```

Do not reset or checkout over uncommitted work. The vulnerable version is
started in a separate worktree.

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected result:

```text
19 passed
```

## 2. Start the vulnerable baseline

The original vulnerable application is commit `4382844`.

```powershell
$vulnerablePath = "C:\Users\alhab\Desktop\9raya\securedesk-vulnerable"
if (-not (Test-Path $vulnerablePath)) {
    git worktree add $vulnerablePath 4382844
}
Set-Location $vulnerablePath
docker build --target runtime --tag securedesk:vulnerable .
docker run -d `
  --name securedesk-vulnerable `
  -p 5051:5000 `
  securedesk:vulnerable
```

Verify it:

```powershell
curl.exe http://127.0.0.1:5051/health
```

Expected:

```json
{"status":"healthy"}
```

Open this URL in the browser:

```text
http://127.0.0.1:5051/login
```

The baseline contains the deliberately introduced vulnerabilities. It is
used only to demonstrate the before state.

## 3. Vulnerability demonstrations

### 3.1 IDOR

1. Log in as `client.demo` / `client123`.
2. Create a ticket and note its ID, for example `1`.
3. Open a private/incognito browser window.
4. Register or log in as another client.
5. Open:

```text
http://127.0.0.1:5051/tickets/1
```

The second client can read the first client's ticket.

Expected baseline evidence:

```text
HTTP 200
```

Explain:

> The vulnerable version trusts the ticket ID and does not enforce ownership.

### 3.2 Stored XSS

Add this comment to a ticket:

```html
<script>alert('Secure Desk XSS')</script>
```

Open:

```text
http://127.0.0.1:5051/api/tickets/1/view
```

The raw script is present and may execute in a browser.

Explain:

> The vulnerable version inserts the stored comment into HTML without escaping.

### 3.3 SQL injection

Create at least two tickets, then open:

```text
http://127.0.0.1:5051/api/tickets/search?q=%27%20OR%201%3D1%20--
```

The search returns unrelated records because the input is concatenated into
the SQL statement.

Explain:

> The search condition is altered by attacker-controlled SQL syntax.

### 3.4 CSRF

After authenticating to the vulnerable API, send a state-changing request
without a CSRF token:

```powershell
curl.exe -i `
  -X POST `
  -H "Content-Type: application/json" `
  -d '{"title":"CSRF baseline","description":"No token"}' `
  http://127.0.0.1:5051/api/tickets
```

The vulnerable version accepts the request.

Explain:

> A cross-site request could trigger a state change because no token is
> required.

### 3.5 Hardcoded secret

The vulnerable image can start without a `SECRET_KEY`:

```powershell
docker run --rm securedesk:vulnerable
```

Explain:

> The baseline uses a development fallback secret instead of requiring a
> production secret from the environment.

## 4. Start the corrected application

Return to the main repository:

```powershell
Set-Location C:\Users\alhab\Desktop\9raya\Devsecops
docker build --target runtime --tag securedesk:demo-secure .
docker run -d `
  --name securedesk-secure `
  -p 5050:5000 `
  -e SECRET_KEY=demo-secure-key `
  securedesk:demo-secure
```

Verify it:

```powershell
curl.exe http://127.0.0.1:5050/health
```

Open:

```text
http://127.0.0.1:5050/login
```

## 5. Show the remediations

Repeat each attack using port `5050`.

| Test | Corrected result |
|---|---|
| Client reads another client's ticket | `404 Ticket not found` |
| Stored comment contains script | Script is HTML-escaped |
| SQL injection search | Empty result for the payload |
| POST without CSRF token | `403 CSRF token required` |
| Missing `SECRET_KEY` | Application refuses production startup |

Test missing secret:

```powershell
docker run --rm securedesk:demo-secure
```

Expected:

```text
SECRET_KEY must be configured
```

Test CSRF:

```powershell
curl.exe -i `
  -X POST `
  -H "Content-Type: application/json" `
  -d '{"title":"CSRF test","description":"No token"}' `
  http://127.0.0.1:5050/api/tickets
```

Expected:

```text
HTTP/1.1 403
```

## 6. Show the automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests cover authentication, role separation, ticket ownership, XSS
escaping, SQL injection prevention, CSRF, security headers, logging, and
secret configuration.

## 7. Show the CI/CD pipeline

Open:

```text
https://github.com/Dabbabi-Rayen/securedesk/actions
```

Show the failed workflow first:

```text
06-github-actions-failed.png
```

Explain that it represents the intentionally vulnerable state.

Then show the successful workflow:

```text
06-github-actions-success.png
```

Point out these jobs:

- Unit tests
- Semgrep SAST
- Gitleaks
- Trivy filesystem scan
- Docker build
- Trivy image scan

## 8. Show Docker hardening

```powershell
docker inspect securedesk:demo-secure --format '{{.Config.User}}'
```

Expected:

```text
app
```

The production image also removes packaging tools from the runtime image and
uses Debian security updates.

Optional image scan:

```powershell
docker run --rm `
  -v //var/run/docker.sock:/var/run/docker.sock `
  aquasec/trivy:latest `
  image `
  --severity HIGH,CRITICAL `
  --ignore-unfixed `
  securedesk:demo-secure
```

## 9. Show Kubernetes hardening

```powershell
kubectl config current-context
kubectl -n securedesk get pods,svc,networkpolicy
kubectl -n securedesk get deployment securedesk -o yaml
```

Point out:

- non-root UID `999`
- read-only root filesystem
- dropped capabilities
- disabled privilege escalation
- RuntimeDefault seccomp profile
- disabled service-account token
- resource requests and limits
- readiness and liveness probes
- persistent storage
- default-deny network policies

Access the deployed application:

```powershell
kubectl -n securedesk port-forward svc/securedesk 5050:5000
```

In another terminal:

```powershell
curl.exe http://127.0.0.1:5050/health
```

## 10. Show security logs

```powershell
kubectl -n securedesk get pods
kubectl -n securedesk logs deployment/securedesk --tail=100
```

Look for structured JSON events such as:

```json
{"event":"ticket.access_denied"}
```

or:

```json
{"event":"ticket.search_suspicious"}
```

Use this screenshot:

```text
20-security-log.png
```

Explain:

> Security events are emitted to standard output so Kubernetes logging systems
> can collect and process them.

## 11. Show the final ZAP result

Show:

```text
21-zap-hardening-after.png
```

The important result is:

```text
FAIL-NEW: 0
```

Point out the passes for:

- Content Security Policy
- anti-clickjacking
- `X-Content-Type-Options`
- Permissions Policy
- SameSite cookie
- CSRF detection

The remaining authentication and session-management notifications are
informational observations, not blocking failures.

## 12. Recommended presentation order

1. Login page and client dashboard.
2. Create a support ticket.
3. Show technician access.
4. Show administrator access.
5. Demonstrate IDOR before and after.
6. Demonstrate stored XSS before and after.
7. Demonstrate SQL injection before and after.
8. Show the failed pipeline.
9. Show the successful pipeline.
10. Show Docker and Kubernetes hardening.
11. Show the final ZAP summary.
12. Show the structured Kubernetes security log.
13. Conclude with the remediation summary.

## 13. Cleanup

Stop both containers:

```powershell
docker rm -f securedesk-vulnerable securedesk-secure
```

Remove the temporary vulnerable worktree after the presentation:

```powershell
Set-Location C:\Users\alhab\Desktop\9raya\Devsecops
git worktree remove ..\securedesk-vulnerable --force
```

Confirm that the main repository was not overwritten:

```powershell
git status --short
git worktree list
```

## Final explanation

Secure Desk started as a deliberately vulnerable Flask helpdesk application.
The vulnerable version demonstrated IDOR, stored XSS, SQL injection, CSRF,
and insecure secret configuration. The corrected version enforces ownership,
escapes HTML, parameterizes SQL, validates CSRF tokens, requires a production
secret, passes regression tests, integrates security scanners, runs as a
non-root container, uses Kubernetes hardening, and produces structured
security logs.
