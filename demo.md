# Secure Desk - Simple Demo Guide

This is the short version of the demo. Use the browser for the application
and use only simple commands for Docker, tests, and Kubernetes.

The vulnerable app uses port `5051`.
The corrected app uses port `5050`.

Only test the vulnerabilities on these local containers.

## 1. Run the tests first

Open **Command Prompt** in the project folder:

```cmd
cd /d C:\Users\alhab\Desktop\9raya\Devsecops
.\.venv\Scripts\python.exe -m pytest
```

Expected:

```text
19 passed
```

## 2. Start the vulnerable app

The vulnerable version is commit `4382844`.

Run these commands once:

```cmd
git worktree add ..\securedesk-vulnerable 4382844
cd ../securedesk-vulnerable
docker build --target runtime -t securedesk:vulnerable .
docker run -d --name securedesk-vulnerable -p 5051:5000 securedesk:vulnerable
```

Check that it is running:

```cmd
curl http://127.0.0.1:5051/health
```

Open in the browser:

```text
http://127.0.0.1:5051/login
```

Use:

```text
client.demo / client123
```

## 3. Show the vulnerable behavior

### IDOR

1. Log in as `client.demo`.
2. Create a ticket and remember its number.
3. Open an incognito browser window.
4. Create or use another client account.
5. Open the first ticket:

```text
http://127.0.0.1:5051/api/tickets/1
```

The second client can read the first client's ticket.

Say:

> The application trusts the ticket ID and does not check ownership.

### Stored XSS

Add this comment:

```html
<script>alert('XSS')</script>
```

Open:

```text
http://127.0.0.1:5051/api/tickets/1/view
```

The script is returned without escaping.

Say:

> The comment is stored and inserted into the page as HTML.

### SQL injection

Create two tickets, then open this URL:

```text
http://127.0.0.1:5051/api/tickets/search?q=%27%20OR%201%3D1%20--
```

The response contains unrelated tickets.

Say:

> The search input changes the SQL condition because it is concatenated into
> the query.

### CSRF

Use the browser developer tools to submit a state-changing request without a
CSRF token. In the vulnerable version, the request is accepted.

Say:

> A request from another website could change data because no token is checked.

### Hardcoded secret

Stop the vulnerable container:

```cmd
docker stop securedesk-vulnerable
```

Start it without a secret:

```cmd
docker run --rm securedesk:vulnerable
```

It still starts because the old version contains a fallback secret.

## 4. Start the corrected app

Open a new Command Prompt:

```cmd
cd /d C:\Users\alhab\Desktop\9raya\Devsecops
docker build --target runtime -t securedesk:secure .
docker run -d --name securedesk-secure -p 5050:5000 -e SECRET_KEY=demo-key securedesk:secure
```

Check it:

```cmd
curl http://127.0.0.1:5050/health
```

Open:

```text
http://127.0.0.1:5050/login
```

## 5. Show the corrected behavior

Repeat the same tests using port `5050`.

| Test | Correct result |
|---|---|
| Client opens another client's ticket | `404 Ticket not found` |
| XSS comment | Displayed as text, no alert |
| SQL injection search | Empty result |
| Request without CSRF token | `403` |
| App without `SECRET_KEY` | Startup fails |

Test the missing secret:

```cmd
docker stop securedesk-secure
docker run --rm securedesk:secure
```

Expected:

```text
SECRET_KEY must be configured
```

Start it again:

```cmd
docker start securedesk-secure
```

## 6. Show the pipeline

Open:

```text
https://github.com/Dabbabi-Rayen/securedesk/actions
```

Show the failed run first:

```text
06-github-actions-failed.png
```

Explain:

> This is the intentionally vulnerable state before remediation.

Then show the successful run:

```text
06-github-actions-success.png
```

Point out:

- tests
- Semgrep
- Gitleaks
- Trivy dependency scan
- Docker build
- Trivy image scan

## 7. Show Docker hardening

```cmd
docker inspect securedesk:secure --format "{{.Config.User}}"
```

Expected:

```text
app
```

Explain that the image runs as a non-root user and removes unnecessary
packaging tools from the production image.

## 8. Show Kubernetes

```cmd
kubectl config current-context
kubectl -n securedesk get pods
kubectl -n securedesk get svc
kubectl -n securedesk get networkpolicy
```

Show the deployment security settings:

```cmd
kubectl -n securedesk get deployment securedesk -o yaml
```

Mention:

- non-root container
- read-only filesystem
- dropped capabilities
- no privilege escalation
- seccomp profile
- health probes
- resource limits
- persistent database volume
- default-deny network policy

Access the Kubernetes app:

```cmd
kubectl -n securedesk port-forward svc/securedesk 5050:5000
```

In another Command Prompt:

```cmd
curl http://127.0.0.1:5050/health
```

## 9. Show the security logs

```cmd
kubectl -n securedesk get pods
kubectl -n securedesk logs deployment/securedesk
```

Look for events such as:

```json
{"event":"ticket.access_denied"}
```

or:

```json
{"event":"ticket.search_suspicious"}
```

Use screenshot:

```text
20-security-log.png
```

Say:

> The application writes structured JSON security events to the container
> output, where Kubernetes can collect them.

## 10. Show ZAP

Show:

```text
21-zap-hardening-after.png
```

Point out:

```text
FAIL-NEW: 0
```

Also show the successful checks for CSP, anti-clickjacking, MIME sniffing,
Permissions Policy, SameSite cookies, and CSRF.

## 11. Recommended presentation order

1. Login page.
2. Client dashboard.
3. Create a ticket.
4. Technician dashboard.
5. Administrator dashboard.
6. IDOR before and after.
7. XSS before and after.
8. SQL injection before and after.
9. Failed pipeline.
10. Successful pipeline.
11. Docker and Kubernetes hardening.
12. ZAP result.
13. Kubernetes security log.

## 12. Cleanup

```cmd
docker rm -f securedesk-vulnerable
docker rm -f securedesk-secure
cd C:\Users\alhab\Desktop\9raya\Devsecops
git worktree remove ..\securedesk-vulnerable --force
```

Check that the main project is still present:

```cmd
git status
```

## Final explanation

> Secure Desk started as a deliberately vulnerable Flask helpdesk application.
> We demonstrated IDOR, stored XSS, SQL injection, CSRF, and insecure secret
> configuration. We then added ownership checks, HTML escaping, parameterized
> SQL, CSRF protection, secure configuration, automated tests, security
> scanning, Docker hardening, Kubernetes hardening, OWASP ZAP validation, and
> structured security logging.
