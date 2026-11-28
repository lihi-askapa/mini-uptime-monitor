# SQLite backup and isolated restore

## Current automatic backup configuration

Daily backups are now installed and enabled on the EC2 host. Terraform created
private bucket `pulse-944464821297-backups-eu-north-1`, blocked public access,
set AES256 server-side encryption, required HTTPS and configured expiration of
objects under `sqlite/` after 30 days (S3 lifecycle deletion is asynchronous).
The EC2 role can upload/abort multipart uploads only under that prefix; it has
no new read, list or delete permission. The bucket is protected against Terraform
removal and force deletion. S3 versioning is not enabled; timestamped keys identify
separate snapshots. This does not back up Terraform state or the entire server.

A systemd timer runs daily at 03:00 UTC plus up to five minutes of random delay
(05:00 in Israel winter, 06:00 in summer). It is enabled across reboots and catches
up after a missed scheduled run when the server comes back. The server must be
running with Docker and the web container available. A failed service retries
after 15 minutes; failures are logged, but no notification channel is configured.
The Mac does not need to stay open. Enabling a timer does not make EC2 start itself.

Files:

- `infra/terraform/backups.tf`: bucket, encryption, lifecycle and scoped IAM policy.
- `scripts/sqlite_snapshot.py`: online snapshot and integrity verification.
- `scripts/scheduled_backup.sh`: snapshot, copy out of Docker, upload DB and metadata,
  save last-success metadata and remove this run's volume snapshot after upload.
- `scripts/pulse-backup.service`: executable, environment, timeout and retry policy.
- `scripts/pulse-backup.timer`: daily schedule and persistence.
- `scripts/install_backup.py`: verifies the personal account and installs the reviewed
  files on the fixed project EC2 host through SSM. It runs the service once to check it.

Host files are installed under `/opt/pulse-backup/` and `/etc/systemd/system/`;
`/etc/pulse-backup.env` contains the bucket name, no credentials. The service uses
the EC2 instance role. Its host flock serializes backups with application deployments.
`/var/lib/mini-uptime-monitor/last-backup.json` records the last successful snapshot.
Host installation is separate from Terraform; applying bucket resources alone does
not install the timer. After source changes, rerun the reviewed installer to update
host files. No application image rebuild is required for these host utilities.

### Verified first service execution

SSM installation command `8edc00c5-a8cb-427a-88e0-b7a507fb42b5` returned Success.
The service completed with Result=success and ExecMainStatus=0. The timer listed
its next run as 2026-11-28 03:00:31 UTC; that future scheduled firing has not yet
been observed. The same service was started immediately for verification.

Uploaded: `s3://pulse-944464821297-backups-eu-north-1/sqlite/checks-20261128T024512Z.db`
and the matching `.db.json` metadata file. The snapshot contains 6,175 checks and
is 675,840 bytes. It was downloaded from S3 to the Mac backup directory, restored
to `checks-20261128T024512Z-s3-restore-check.db` and checked: native S3 SHA256,
metadata SHA256, SQLite integrity, full restored SQL contents, Flask dashboard
and `/health` all passed. The public scheduler-health endpoint remained ok.
SHA256: `79b4b59b45debdfc97b1a69e5d8cde1935699a58d4a9ef09716d18959c180339`.
Private verification JSON is stored beside the Mac copy, outside Git. Application
tests remain fifteen. Terraform apply added seven resources; follow-up plan is checked separately.

Inspect from an SSH shell:

```bash
sudo systemctl list-timers pulse-backup.timer --no-pager
sudo systemctl status pulse-backup.service --no-pager
sudo journalctl -u pulse-backup.service -n 20 --no-pager -l
```

A successful oneshot service normally becomes inactive after it finishes; check
Result/exit status and logs. S3 retrieval and restoration use an authorized operator
identity, not the upload-only EC2 policy. Restores are still rehearsed into isolated
copies; automatic production replacement is not configured.

## Initial one-time exercise: 2026-11-28

The running EC2 database was snapshotted using SQLite's online backup API,
without stopping the application or copying the live database file directly.
The snapshot is a standalone SQLite `.db` file containing all three tables.
It is not a ZIP archive, SQL export or continuously updated replica.

Verified snapshot: `checks-20261128T023904Z.db` (04:39 Israel time).

| Check | Result |
|---|---|
| Snapshot size | 671,744 bytes |
| Stored checks | 6,157 |
| Other tables | 2 manual-check limits; 1 scheduler-state row |
| SQLite integrity | `ok` |
| SHA256 after transfer | Matches the server snapshot |
| Isolated restore | All table counts and full SQL dump match the backup |
| Flask using restored database | Dashboard and `/health` both returned 200 |
| Live service after backup | Monitoring health returned `ok` |

SHA256: `776adcc3318491f7c9e3b92ac2f4b991d4909fc9ab802f3a8dc534833d7f4d49`.

## Locations

- EC2 host: `/home/ec2-user/pulse-backups/checks-20261128T023904Z.db`.
- Application volume also retains `/app/data/backups/checks-20261128T023904Z.db`.
- Mac: `/Users/lihias/Documents/Codex/pulse-backups/checks-20261128T023904Z.db`.
- Isolated Mac restore: the adjacent `checks-20261128T023904Z-restore-check.db`.
- Private verification report: the adjacent `checks-20261128T023904Z.verification.json`.

The Mac files are outside the project repository. Database files have owner-only
permissions. An EC2 host copy alone would be lost with the host disk; the Mac copy
is outside that failure domain. These initial copies predate the automatic S3 setup described above.

## Reusable snapshot helper

`scripts/sqlite_snapshot.py` uses only Python's standard library. It opens the
source read-only, calls `Connection.backup`, checks integrity and required tables,
and prints counts, size and SHA256. Existing destinations are rejected. New files
are owner-only; a failed snapshot is removed. It also works with an open WAL database.

Example isolated restoration on the Mac, from the repository root:

```bash
python3 scripts/sqlite_snapshot.py \
  /Users/lihias/Documents/Codex/pulse-backups/checks-20261128T023904Z.db \
  /Users/lihias/Documents/Codex/pulse-backups/another-isolated-restore.db
```

For a live snapshot, run the helper inside the web container against
`/app/data/checks.db`, selecting a new timestamped destination under
`/app/data/backups/`. Then copy the finished snapshot out using `docker cp` and
transfer it off the server. Compare its SHA256 after transfer and exercise the
restored data before relying on it. The helper does not itself perform SSM,
SSH, SCP, scheduling or uploads.

## Scope

This was a one-time backup and non-destructive restore exercise. The original
live database was not replaced. The restored scheduler timestamp is historical;
it should not be expected to pass monitoring freshness checks until a scheduler
runs against that copy. That initial exercise did not configure automation. Scheduled encrypted S3 backups
with retention were subsequently installed as described above; automated production recovery is not configured. Production replacement would need
its own coordinated stop/restore/ownership/start procedure and recovery checks.

[Python SQLite backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)
