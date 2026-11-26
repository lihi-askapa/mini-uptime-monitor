# Pulse — Mini Uptime Monitor

A small DevOps learning project by **Lihi Askapa**: build it, explain it, break it, investigate it.

## Stage 1: local application

- Python + Flask, server-rendered HTML/CSS, SQLite.
- Check configured websites on demand; record HTTP status, duration and UTC timestamp.
- Display the latest result per target and the last 50 historical checks.
- `GET /health` checks this application and database readability, independently of target status.
- HTTP 200–399 is classified as up; other codes and connection failures as down. Redirects are followed by Python's HTTP client.
- Duration measures time to receive response headers, not complete page load.

## Run

```bash
python3 -m venv .venv
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
the same five unittest tests used locally. The tests use mocked HTTP responses and
temporary databases; they do not check the live websites or use the application volume.

The workflow starts running after the file is committed and pushed to GitHub.
After the Python tests pass, it builds `mini-uptime-monitor:ci` and runs the same
tests inside a temporary container from that image. No image is published and
the application is not deployed. See [the CI lab in Hebrew](docs/ci-lab.md).

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

`POST /checks` accepts a configured target ID, not an arbitrary URL. Only configure endpoints you are permitted to check. Each click performs one synchronous request; there is no scheduler, uptime percentage or alert delivery yet. The latest result is a historical observation, not a guarantee of present availability.

## Deployment boundary

This is a localhost learning application with no authentication, CSRF protection or rate limiting. Direct `python app.py` uses Flask's development server; Docker uses Gunicorn with local-only port publishing and resource limits. Public deployment still needs authentication/CSRF decisions, rate limiting, restricted egress (including redirect targets) and concurrency/load validation. Do not expose the development server publicly.

## Learning roadmap

- [x] Local application, SQLite history, health endpoint, logs and tests
- [x] Docker image, environment variables and persistent volume
- [ ] Failure investigation exercises
- [x] GitHub Actions Python tests
- [ ] GitHub Actions image build and container tests (workflow prepared; remote run pending)
- [ ] AWS training deployment and Terraform module
- [ ] AI-assisted review workflow with human approval

See [learning notes](docs/learning-notes.md). Only completed stages should be described as hands-on experience in an interview.
