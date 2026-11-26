"""A small, on-demand HTTP monitor. Run locally with: python3 app.py."""
import json
import logging
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import click
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for


def create_app(test_config=None):
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE_PATH", str(Path(__file__).parent / "data/checks.db")),
        TARGETS=json.loads(os.environ.get("MONITOR_TARGETS", json.dumps({
            "example": {"name": "Example website", "url": "https://example.com"},
            "portfolio": {"name": "Lihi's portfolio", "url": "https://lihi-portfolio-site.onrender.com/"},
            "ogdan": {"name": "Ogdan Mehandesim", "url": "https://ogdan-mehandesim.onrender.com/"},
        }))),
        REQUEST_TIMEOUT=float(os.environ.get("REQUEST_TIMEOUT", "5")),
        PUBLIC_DEMO=os.environ.get("PUBLIC_DEMO", "0") == "1",
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=16384,
    )
    if test_config:
        app.config.update(test_config)
    if app.config["PUBLIC_DEMO"]:
        app.config.update(SESSION_COOKIE_SECURE=True, SESSION_COOKIE_SAMESITE="Lax")
    for target in app.config["TARGETS"].values():
        parsed = urlparse(target["url"])
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Targets must be HTTP(S) URLs without embedded credentials")
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        db = sqlite3.connect(app.config["DATABASE"], timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY, target_id TEXT NOT NULL, target_name TEXT NOT NULL,
            url TEXT NOT NULL, checked_at TEXT NOT NULL, status TEXT NOT NULL,
            status_code INTEGER, response_ms REAL NOT NULL, error TEXT
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS manual_check_limits (
            target_id TEXT PRIMARY KEY, allowed_after REAL NOT NULL
        )""")

    @app.get("/")
    def index():
        csrf_token = ""
        if app.config["PUBLIC_DEMO"]:
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_hex(32)
            csrf_token = session["csrf_token"]
        with connect() as db:
            history = db.execute("SELECT * FROM checks ORDER BY id DESC LIMIT 50").fetchall()
            latest = {r["target_id"]: r for r in db.execute("""
                SELECT * FROM checks WHERE id IN
                (SELECT MAX(id) FROM checks GROUP BY target_id)
            """)}
        counts = {state: sum(key in latest and latest[key]["status"] == state
                  for key in app.config["TARGETS"]) for state in ("up", "down")}
        return render_template("index.html", targets=app.config["TARGETS"],
                               latest=latest, history=history, counts=counts,
                               csrf_token=csrf_token)

    def check_target(target_id):
        target = app.config["TARGETS"][target_id]
        started = time.monotonic()
        code, error = None, None
        try:
            req = Request(target["url"], headers={"User-Agent": "MiniUptimeMonitor/0.1"})
            with urlopen(req, timeout=app.config["REQUEST_TIMEOUT"]) as response:
                code = response.status
        except HTTPError as exc:
            code = exc.code
            error = f"HTTP {code}"
        except (URLError, TimeoutError, OSError) as exc:
            error = str(getattr(exc, "reason", exc))[:240]
        elapsed = round((time.monotonic() - started) * 1000, 1)
        state = "up" if code is not None and 200 <= code < 400 else "down"
        with connect() as db:
            db.execute("""INSERT INTO checks
                (target_id,target_name,url,checked_at,status,status_code,response_ms,error)
                VALUES (?,?,?,?,?,?,?,?)""", (target_id, target["name"], target["url"],
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                state, code, elapsed, error))
        app.logger.info("check target=%s status=%s http=%s duration_ms=%s", target_id, state, code, elapsed)

    @app.post("/checks")
    def run_check():
        target_id = request.form.get("target_id", "")
        if target_id not in app.config["TARGETS"]:
            abort(400, "Choose a configured target")
        if app.config["PUBLIC_DEMO"]:
            supplied = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not secrets.compare_digest(supplied, expected):
                abort(400, "Reload the page and use its Check now button.")
            # A shared SQLite transaction prevents concurrent visitors from
            # claiming the same target's 30-second slot, even across app instances.
            now = time.time()
            with connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT allowed_after FROM manual_check_limits WHERE target_id=?",
                                 (target_id,)).fetchone()
                if row and row["allowed_after"] > now:
                    return "This target was checked recently. Please wait 30 seconds and go back.", 429, {"Retry-After": "30"}
                db.execute("INSERT OR REPLACE INTO manual_check_limits (target_id,allowed_after) VALUES (?,?)",
                           (target_id, now + 30))
        check_target(target_id)
        return redirect(url_for("index"), code=303)

    @app.cli.command("monitor")
    @click.option("--interval", default=60, type=click.IntRange(min=10), show_default=True,
                  help="Seconds to wait after each complete round.")
    @click.option("--once", is_flag=True, help="Run one round and exit.")
    def monitor(interval, once):
        """Check all configured targets sequentially, then wait and repeat."""
        while True:
            app.logger.info("Scheduled check round started")
            for target_id in app.config["TARGETS"]:
                check_target(target_id)
            if once:
                return
            app.logger.info("Scheduled round finished; waiting %s seconds", interval)
            time.sleep(interval)

    @app.get("/health")
    def health():
        # Health of this application, independent of the websites being checked.
        try:
            with connect() as db:
                db.execute("SELECT id FROM checks LIMIT 1").fetchall()
        except sqlite3.Error:
            app.logger.exception("Database health check failed")
            return jsonify(status="degraded", database="unavailable"), 503
        return jsonify(status="ok", database="reachable", version="0.1.0")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    create_app().run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")))
