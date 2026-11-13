# Secure Desk

Secure Desk is a deliberately small Flask helpdesk web application for the
DevSecOps project. It supports clients, technicians, and administrators while
keeping the application scope focused on secure delivery, testing, and
demonstration.

## Current status

The application foundation is complete:

- Flask web application with server-rendered HTML templates.
- SQLite persistence.
- Login/logout and three demo roles.
- Ticket creation, listing, details, and comments.
- JSON API for the same core ticket workflow.
- Five intentional vulnerabilities reserved for the security phases.
- Docker and Docker Compose deployment.
- GitHub Actions security workflow.
- Hardened Kubernetes deployment with persistent storage and network policies.
- Initial public and authenticated DAST scans with OWASP ZAP.
- IDOR remediation in the application source with regression tests.
- Stored XSS remediation in the HTML ticket view with regression tests.
- SQL injection remediation with parameterized ticket search queries.

The remaining phases are structured logging, incident-response evidence, and
remediation of the remaining intentional findings.

## Repository

GitHub: <https://github.com/Dabbabi-Rayen/securedesk>

Default branch: `main`

## Application routes

| Route | Purpose |
| --- | --- |
| `/login` | Web login |
| `/signup` | Client self-registration |
| `/staff/login` | Separate technician/admin login |
| `/dashboard` | Ticket dashboard |
| `/staff` | Technician/admin ticket desk |
| `/admin` | Admin user directory |
| `/tickets/new` | Create a ticket |
| `/tickets/<id>` | View a ticket and add comments |
| `/health` | Health check |

## Ticket API

- `POST /api/tickets` with `title` and `description` JSON fields
- `GET /api/tickets`
- `GET /api/tickets/<id>`
- `POST /api/tickets/<id>/comments`
- `GET /api/tickets/<id>/view`

## Deliberate security findings for the project

The initial training version contained five findings for the DevSecOps phases.
The IDOR, stored XSS, and SQL injection findings have now been remediated in
the source code and are covered by regression tests. The remaining training
findings are:

- **Hardcoded secret:** the Flask `SECRET_KEY` uses a committed fallback value.
- **Missing CSRF protection:** authenticated state-changing requests do not
  require a CSRF token.

| Finding | OWASP category | Demonstration endpoint |
| --- | --- | --- |
| Hardcoded secret | A05 Security Misconfiguration | Application configuration |
| Missing CSRF | A05 Security Misconfiguration | `POST /api/tickets` |

These are fictitious findings on the local Secure Desk application only. They
must not be tested against any third-party system.

Demo accounts use fictitious local-only credentials:

| Username | Password | Role |
| --- | --- | --- |
| `client.demo` | `client123` | Client |
| `tech.demo` | `tech123` | Technician |
| `admin.demo` | `admin123` | Admin |

## Local setup

From the project directory:

```powershell
cd C:\Users\alhab\Desktop\9raya\Devsecops
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements-dev.txt
```

Run the tests:

```powershell
py -m pytest
```

Start the application:

```powershell
py run.py
```

Open <http://127.0.0.1:5000/> in a browser. It redirects to the client login
page.

The health endpoint is available at:

<http://127.0.0.1:5000/health>

## Testing the web app

### Client

1. Open `/login`, or choose **Create a client account** to use `/signup`.
2. Sign in with `client.demo` / `client123`, or use the account you registered.
3. Create a support ticket, open it, and add a comment.

### Staff and administrator

1. Open `/staff/login`; staff accounts cannot sign in through the client login.
2. Sign in with `tech.demo` / `tech123` to open the staff desk.
3. Sign in with `admin.demo` / `admin123` to access the staff desk and the
   administrator user directory at `/admin`.

All credentials are fictitious and local-only. They must never be reused as
real credentials.

## GitHub

Configure the Git identity if needed:

```powershell
git config user.name "rayen.dabbabi"
git remote -v
git push origin main
```

The configured remote is:

```text
https://github.com/Dabbabi-Rayen/securedesk.git
```

## Run with Docker

Build and start the container:

```powershell
docker compose up --build
```

Open <http://127.0.0.1:5000/login>. The SQLite database is stored in the
`securedesk-data` named volume. Stop the application with:

```powershell
docker compose down
```

The image uses a multi-stage build, runs as the unprivileged `app` user, drops
Linux capabilities, enables `no-new-privileges`, and mounts the database
directory separately so the application filesystem can remain read-only.

## CI/CD security pipeline

The GitHub Actions workflow is defined in
[.github/workflows/security.yml](./.github/workflows/security.yml). It runs on
pushes to `main`, pull requests, or manually from
the Actions tab. It intentionally blocks on failed tests, SAST findings,
detected secrets, high or critical dependency vulnerabilities, and high or
critical image vulnerabilities.

The current training version is expected to fail security jobs because the
five findings are intentionally present. The failure is part of the evidence:
we will capture the results, remediate the application, and require the
pipeline to pass afterward.

### GitHub setup

GitHub Actions uses its hosted Ubuntu runner, so no local runner is required.
Create a GitHub repository and push this project to it. Then open the
repository's **Actions** tab and run **Secure Desk security pipeline** manually,
or push to `main`.

The workflow only requests `contents: read` and uses the automatically
provided `GITHUB_TOKEN`. No registry passwords or scanner credentials are
required.

## Kubernetes deployment

The local Kubernetes manifests are in [k8s/](./k8s/). They use a single
replica because the current application stores its SQLite database on a
persistent volume.

Build the image and create the local secret:

```powershell
docker build --target runtime --tag securedesk:local .
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic securedesk-secrets `
  --namespace securedesk `
  --from-literal=SECRET_KEY="$(New-Guid)-securedesk-local" `
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k k8s/
```

`k8s/secret.example.yaml` is documentation only and is intentionally not
included in the Kustomize resources. Never commit a real secret or apply the
example value in a shared environment.

For Minikube, load the image before applying the manifests:

```powershell
minikube image load securedesk:local
```

Check the deployment and access the app:

```powershell
kubectl -n securedesk get pods,svc,networkpolicy
kubectl -n securedesk port-forward svc/securedesk 5000:5000
```

The deployment runs as UID 999, drops all Linux capabilities, disables
privilege escalation, uses a read-only root filesystem, disables automatic
service-account-token mounting, mounts a memory-backed temporary directory for
Gunicorn, and applies default-deny ingress/egress network policies.

## DAST with OWASP ZAP

OWASP ZAP Baseline scans were executed only against the local Kubernetes
instance through a temporary port-forward. Two scans were performed:

- An unauthenticated scan covering the public application pages.
- An authenticated scan using a temporary local client session, covering the
  client dashboard and ticket pages.

The scans reported missing security headers and the absence of CSRF tokens.
The authenticated scan discovered 16 URLs and reported 10 alert types,
including:

- Missing anti-CSRF tokens.
- Missing Content Security Policy and anti-clickjacking headers.
- Missing `X-Content-Type-Options` and Permissions Policy headers.
- Missing or invalid Cross-Origin security headers.
- A session cookie without `SameSite`.

These results represent the initial, pre-remediation security baseline. The
reports are generated locally and are intentionally excluded from Git because
they may contain local URLs and session-related evidence. The remaining
targeted DAST checks confirmed the baseline IDOR, stored XSS, and SQL
injection findings. All three fixes were rebuilt, redeployed, and verified with
after-remediation checks.

### Reproduce the public ZAP scan

Start the local port-forward in one terminal and leave it running:

```powershell
kubectl -n securedesk port-forward svc/securedesk 5050:5000
```

In another terminal, verify the application:

```powershell
curl.exe http://127.0.0.1:5050/health
```

The expected response is:

```json
{"status":"healthy"}
```

Run the ZAP Baseline scan from the repository root. Docker Desktop is required:

```powershell
$workspace = (Get-Location).Path
docker run --rm `
  -v "${workspace}:/zap/wrk/:rw" `
  -t zaproxy/zap-stable `
  zap-baseline.py `
  -t http://host.docker.internal:5050 `
  -r zap-baseline.html `
  -J zap-baseline.json `
  -I
```

The HTML and JSON reports are local evidence only. They are excluded from Git.
The first run downloads the ZAP image and can take several minutes.

### Reproduce the authenticated scan

The authenticated scan uses a temporary client session. Do not copy a real
session cookie into the repository or into a shared command history. The
session can be created through the web login:

```powershell
$cookiePath = Join-Path $env:TEMP "securedesk-zap-cookie.txt"
curl.exe -sS -L `
  -c $cookiePath `
  -o NUL `
  -d "username=client.demo&password=client123" `
  http://127.0.0.1:5050/login
```

The cookie can be supplied to ZAP with a temporary Replacer rule for the
`Cookie` request header. In the ZAP desktop interface, browse the application
through the local proxy first, then include the local site in a context and
run the spider and passive scan. For the Docker Baseline scan, provide the
temporary value as a replacement in the command below:

```powershell
$sessionCookie = "<temporary-session-cookie-value>"
$workspace = (Get-Location).Path
docker run --rm `
  -v "${workspace}:/zap/wrk/:rw" `
  -t zaproxy/zap-stable `
  zap-baseline.py `
  -t http://host.docker.internal:5050/dashboard `
  -r zap-authenticated.html `
  -J zap-authenticated.json `
  -I `
  -z "-config replacer.full_list(0).description=client-session -config replacer.full_list(0).enabled=true -config replacer.full_list(0).matchtype=REQ_HEADER -config replacer.full_list(0).matchstr=Cookie -config replacer.full_list(0).regex=false -config replacer.full_list(0).replacement=session=$sessionCookie"
```

Afterward, remove the temporary cookie:

```powershell
Remove-Item $cookiePath -Force -ErrorAction SilentlyContinue
```

The authenticated scan should discover the client dashboard and ticket pages,
including `/dashboard`, `/tickets/<id>`, and `/tickets/new`.

### Reproduce the targeted vulnerability checks

These checks are deliberately performed only against the local Secure Desk
instance. They use the normal web forms for authentication and test data, then
read the API responses with the resulting local session.

1. Start the port-forward shown above.
2. Log in locally as `client.demo` and `tech.demo`.
3. As the client, create a test ticket and record its numeric ID.
4. As the technician, request the client's ticket:

```text
GET http://127.0.0.1:5050/api/tickets/<ticket-id>
```

Before remediation, an HTTP `200` response containing the ticket confirms the
IDOR finding.

To reproduce the browser-visible **before** state without changing the main
working tree, use the commit immediately before the IDOR fix
(`dc11ea2`) in a temporary Git worktree:

```powershell
cd C:\Users\alhab\Desktop\9raya\Devsecops
git worktree add ..\securedesk-before-idor dc11ea2
cd ..\securedesk-before-idor
docker build --target runtime --tag securedesk:idor-before .
kubectl -n securedesk set image deployment/securedesk securedesk=securedesk:idor-before
kubectl -n securedesk rollout status deployment/securedesk
kubectl -n securedesk port-forward svc/securedesk 5050:5000
```

In the browser, log in as `client.demo`, create a ticket, and note its ID.
Log out, sign in as another client, and open
`http://127.0.0.1:5050/tickets/<ticket-id>`. The vulnerable version displays
the first client's ticket. Capture this result as `12-idor-before.png`.

Stop the port-forward with `Ctrl+C`, rebuild the current corrected source, and
restore the deployment:

```powershell
cd C:\Users\alhab\Desktop\9raya\Devsecops
docker build --target runtime --tag securedesk:idor-fix .
kubectl -n securedesk set image deployment/securedesk securedesk=securedesk:idor-fix
kubectl -n securedesk rollout status deployment/securedesk
git worktree remove ..\securedesk-before-idor
```

Repeat the browser request with a second client. The corrected version returns
`Ticket not found` (HTTP `404`); capture it as `13-idor-after.png`.

5. Add this harmless training marker as a comment to reproduce the original
   stored XSS finding:

```html
<script>alert("DAST-XSS")</script>
```

Then open:

```text
GET http://127.0.0.1:5050/api/tickets/<ticket-id>/view
```

Before remediation, the raw `<script>` element in the response confirms the
stored XSS finding.

After the XSS remediation, repeat the same request. The script must be
displayed as escaped text and must not execute. Capture this result as
`16-xss-after.png`.

6. With an authenticated session, search with this local test value:

```text
GET /api/tickets/search?q=' OR 1=1 --
```

Before remediation, returning all available tickets instead of only matching
records confirms the SQL injection finding.

After the SQL injection remediation, the same request must be treated as a
literal search value and return an empty list (`[]`). Capture this result as
`17-sqli-after.png`.

The hardcoded secret is validated by Semgrep/Gitleaks and source inspection,
not by a browser DAST request. The missing CSRF protection is visible in the
ZAP alert `10202` and can also be checked by submitting a state-changing
request without a CSRF token.

After testing, stop the port-forward with `Ctrl+C`. The test tickets and
comments are stored in the Kubernetes SQLite PVC and are intentionally kept
as local evidence until the environment is reset.

## DevSecOps roadmap

1. Complete targeted after-remediation checks for IDOR and stored XSS.
2. Fix the remaining CSRF and hardcoded-secret findings.
3. Add safe structured logging, attack detection, and incident-response
   evidence.
4. Rerun the tests and security pipeline and document the before/after results.

Only scan and test the local Secure Desk instance owned by the project team.
