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

The remaining phases are targeted DAST validation, structured logging, incident
response evidence, and vulnerability remediation.

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

The current training version intentionally contains five findings that will be
detected and fixed during the DevSecOps phases:

- **IDOR / broken object-level authorization:** an authenticated user can read
  another client's ticket by changing the ticket ID.
- **Stored XSS:** a comment is rendered without escaping on the HTML ticket
  view.
- **SQL injection:** the ticket search query interpolates the `q` parameter.
- **Hardcoded secret:** the Flask `SECRET_KEY` uses a committed fallback value.
- **Missing CSRF protection:** authenticated state-changing requests do not
  require a CSRF token.

| Finding | OWASP category | Demonstration endpoint |
| --- | --- | --- |
| IDOR | A01 Broken Access Control | `GET /api/tickets/<id>` |
| Stored XSS | A03 Injection | `GET /api/tickets/<id>/view` |
| SQL injection | A03 Injection | `GET /api/tickets/search?q=...` |
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
targeted DAST checks must validate the intentional IDOR, stored XSS, and SQL
injection findings through their specific application and API workflows.

## DevSecOps roadmap

1. Complete targeted DAST validation for IDOR, stored XSS, and SQL injection.
2. Add safe structured logging, attack detection, and incident-response
   evidence.
3. Fix the five intentional vulnerabilities.
4. Rerun the tests and security pipeline and document the before/after results.

Only scan and test the local Secure Desk instance owned by the project team.
