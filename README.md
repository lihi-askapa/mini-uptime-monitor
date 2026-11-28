# Pulse — Mini Uptime Monitor

A small DevOps learning project by **Lihi Askapa**: build it, explain it, break it, investigate it.

**[Open the live demo](https://pulse-13-60-191-46.sslip.io/)** — hosted on AWS EC2
with Docker Compose and Caddy HTTPS. Checks are limited to three configured sites;
manual checks share a 30-second per-target cooldown. Refresh to see scheduled results.
This learning demo is available while the EC2 server is running; its IP-based
hostname may change after a server stop/start.

## Project planning and context

- [Project plan](docs/PLANNING.md): completed stages, upcoming work and completion criteria.
- [Project context](docs/CONTEXT.md): architecture, environments, file responsibilities and where to resume.
- [Learning notes](docs/learning-notes.md): the chronological record of exercises and troubleshooting.

## Stage 1: local application

- Python + Flask, server-rendered HTML/CSS, SQLite.
- Check configured websites on demand; record HTTP status, duration and UTC timestamp.
- Display the latest result per target and the last 50 historical checks.
- `GET /health` checks this application and database readability, independently of target status.
- HTTP 200–399 is classified as up; other codes and connection failures as down. Redirects are followed by Python's HTTP client.
- Duration measures time to receive response headers, not complete page load.

## Run

Use Python 3.12 (as in Docker and CI). The single `requirements.txt` includes both
Flask and Gunicorn; do not use the Mac's older system Python for installation.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8080 and click **Check now**. Stop with Ctrl+C.

```bash
python -m unittest discover -s tests -v
curl http://127.0.0.1:8080/health
```

## Stage 2: Docker

```bash
docker compose up -d --build --wait
docker compose ps
```

Open http://127.0.0.1:8081. Docker runs Gunicorn as a non-root user and stores SQLite in a named volume. This history is separate from the local Python history. See the [Docker lab in Hebrew](docs/docker-lab.md) for ports, logs, persistence and troubleshooting.

## Stage 3: continuous integration

The workflow in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pushes,
pull requests and manual requests from the GitHub Actions tab. An Ubuntu runner
downloads the repository, sets up Python 3.12, installs `requirements.txt` and runs
the same unittest tests used locally. The tests use mocked HTTP responses and
temporary databases; they do not check the live websites or use the application volume.

The workflow starts running after the file is committed and pushed to GitHub.
After the Python tests pass, it builds `mini-uptime-monitor:ci` and runs the same
tests inside a temporary container from that image. No image is published and
the application is not deployed. See [the CI lab in Hebrew](docs/ci-lab.md).

The next workflow revision is prepared to publish the tested `linux/amd64` image
to the private project ECR repository after successful main-branch checks. It uses
GitHub OIDC and a narrowly scoped IAM role, with commit-SHA image tags. Pull requests
and other branches run checks without publishing. This revision still needs a commit,
push and a successful remote run; it does not update EC2.

## Optional scheduled monitoring

The `monitor` CLI command reuses the web button's check-and-save function. The
optional Compose service `scheduler` runs it in a separate container with the same
image and SQLite volume. It checks all configured targets sequentially, waits 60
seconds after the round finishes, then repeats. The first round starts immediately.
This is not an exact once-per-minute schedule. Refresh the browser to see new rows.

After rebuilding the image (see the Docker lab for the local offline build):

```bash
docker compose --profile monitoring up -d
docker compose logs --tail=20 scheduler
docker compose stop scheduler
```

The last command stops background checks while leaving `web` running. The scheduler
has no HTTP listener or health check. Run one instance; there is no leader election,
automatic restart or alerting. Configure targets consistently in both services if
overriding defaults. A database failure stops the worker and is visible in its logs.
Stopping Docker stops monitoring. History has no retention limit yet; stop the
worker after the exercise.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Application listener |
| `HOST` | `127.0.0.1` | Local interface; later use `0.0.0.0` inside Docker |
| `DATABASE_PATH` | `data/checks.db` beside app.py | Persistent SQLite file |
| `REQUEST_TIMEOUT` | `5` | HTTP socket timeout in seconds, not a strict total request deadline |
| `MONITOR_TARGETS` | Example + portfolio + Ogdan Mehandesim | JSON mapping of target IDs to name/URL |

Example: `PORT=8081 python app.py`. `.env.example` is a reference; no automatic dotenv loader is used.

## Request path

Browser → Flask → configured website → SQLite → rendered result.

`POST /checks` accepts a configured target ID, not an arbitrary URL. Only configure endpoints you are permitted to check. Each click performs one synchronous request; optional background checks use the scheduler described above. There is no uptime percentage or alert delivery yet. The latest result is a historical observation, not a guarantee of present availability.

## Deployment boundary

The default configuration is a localhost learning application without authentication.
Direct `python app.py` uses Flask's development server; Docker uses Gunicorn with
local-only port publishing and resource limits. Do not expose the development server publicly.

The public demo configuration is defined in `compose.public.yaml` and
`Caddyfile`, with HTTPS, session form tokens and a shared 30-second per-target manual
check cooldown. Ten tests passed inside the EC2 image. The user verified the public
HTTPS page, a successful manual check and rejection of a repeated check.
See [the public demo guide in Hebrew](docs/public-demo.md). This is a small demo,
without DDoS protection, automatic history retention or general-purpose URL input.

## Learning roadmap

- [x] Local application, SQLite history, health endpoint, logs and tests
- [x] Docker image, environment variables and persistent volume
- [x] Intentional CI failure, log investigation and repair
- [x] GitHub Actions Python tests
- [x] GitHub Actions image build and container tests (green run confirmed by the user)
- [x] Scheduled checks (seven unit tests passed; repeated container rounds confirmed in logs)
- [x] Manual AWS EC2 deployment and public HTTPS demo
- [ ] Terraform module
- [ ] Automated deployment (CD)
- [ ] AI-assisted review workflow with human approval

See [learning notes](docs/learning-notes.md). Only completed stages should be described as hands-on experience in an interview.
