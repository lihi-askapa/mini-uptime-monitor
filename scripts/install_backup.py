"""Install the reviewed daily backup files on the fixed project EC2 host via SSM.

Run from the Mac: python3 scripts/install_backup.py
Requires the backup Terraform resources to have been applied first.
"""
import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AWS = ["aws", "--profile", "pulse-personal", "--region", "eu-north-1"]


def main():
    identity = json.loads(subprocess.check_output(
        AWS + ["sts", "get-caller-identity", "--output", "json"], text=True))
    if identity["Account"] != "944464821297":
        raise RuntimeError("Refusing to configure a different AWS account")

    commands = ["set -eu", "umask 077", "install -d -m 700 /opt/pulse-backup"]
    files = [
        ("scripts/sqlite_snapshot.py", "/opt/pulse-backup/sqlite_snapshot.py", "600"),
        ("scripts/scheduled_backup.sh", "/opt/pulse-backup/backup.sh", "700"),
        ("scripts/pulse-backup.service", "/etc/systemd/system/pulse-backup.service", "644"),
        ("scripts/pulse-backup.timer", "/etc/systemd/system/pulse-backup.timer", "644"),
    ]
    for source, destination, mode in files:
        payload = base64.b64encode((ROOT / source).read_bytes()).decode("ascii")
        commands += [f"printf '%s' '{payload}' | base64 -d > {destination}",
                     f"chmod {mode} {destination}"]
    commands += [
        "printf '%s\\n' 'BACKUP_BUCKET=pulse-944464821297-backups-eu-north-1' > /etc/pulse-backup.env",
        "chmod 600 /etc/pulse-backup.env",
        "systemd-analyze verify /etc/systemd/system/pulse-backup.service /etc/systemd/system/pulse-backup.timer",
        "systemctl daemon-reload",
        "systemctl enable --now pulse-backup.timer",
        "systemctl start pulse-backup.service",
        "systemctl show pulse-backup.service -p Result -p ExecMainStatus",
        "systemctl list-timers pulse-backup.timer --no-pager",
        "cat /var/lib/mini-uptime-monitor/last-backup.json",
        "journalctl -u pulse-backup.service -n 5 --no-pager -l",
    ]
    result = subprocess.check_output(AWS + [
        "ssm", "send-command", "--instance-ids", "i-07451294bf374f84c",
        "--document-name", "AWS-RunShellScript",
        "--parameters", json.dumps({"commands": commands, "executionTimeout": ["700"]}),
        "--comment", "Install daily SQLite S3 backup and verify first run",
        "--query", "Command.CommandId", "--output", "text",
    ], text=True)
    print(result.strip())


if __name__ == "__main__":
    main()
