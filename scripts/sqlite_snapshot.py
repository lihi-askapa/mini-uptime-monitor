"""Create and verify a SQLite snapshot without overwriting an existing file.

Usage: python3 scripts/sqlite_snapshot.py SOURCE DESTINATION
The same operation can restore a backup into a new, isolated database file.
"""
import argparse
import hashlib
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def snapshot(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects the live database and all existing backups.
    destination.touch(mode=0o600, exist_ok=False)
    try:
        deadline = time.monotonic() + 60

        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise TimeoutError("Snapshot exceeded 60 seconds")

        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as src:
            with closing(sqlite3.connect(destination, timeout=5)) as dst:
                src.backup(dst, pages=256, progress=progress, sleep=0.1)
                if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise RuntimeError("SQLite integrity check failed")
                counts = {}
                for table in ("checks", "manual_check_limits", "monitor_state"):
                    counts[table] = dst.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        return {
            "path": str(destination),
            "integrity": "ok",
            "rows": counts,
            "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(json.dumps(snapshot(args.source, args.destination), sort_keys=True))
