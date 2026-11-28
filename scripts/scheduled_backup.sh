#!/usr/bin/env bash
# Installed as /opt/pulse-backup/backup.sh; run by pulse-backup.service.
set -euo pipefail
umask 077
: "${BACKUP_BUCKET:?Set BACKUP_BUCKET in /etc/pulse-backup.env}"
export AWS_REGION=eu-north-1 AWS_DEFAULT_REGION=eu-north-1 AWS_PAGER=''

exec 9>/var/lock/mini-uptime-monitor-deploy.lock
# Serialize with deployments, which might otherwise recreate the source container.
flock -w 120 9 || { echo "Deployment still running; backup deferred to next run." >&2; exit 1; }

name="checks-$(date -u +%Y%m%dT%H%M%SZ).db"
work=$(mktemp -d /var/tmp/pulse-backup.XXXXXXXX)
trap 'rm -rf "$work"' EXIT

timeout 90 docker exec -i mini-uptime-monitor-web-1 python - \
  /app/data/checks.db "/app/data/backups/$name" \
  < /opt/pulse-backup/sqlite_snapshot.py > "$work/$name.json"
docker cp "mini-uptime-monitor-web-1:/app/data/backups/$name" "$work/$name"
digest=$(sha256sum "$work/$name" | cut -d ' ' -f 1)

aws s3 cp "$work/$name" "s3://$BACKUP_BUCKET/sqlite/$name" \
  --region "$AWS_REGION" --sse AES256 --checksum-algorithm SHA256 \
  --metadata "sha256=$digest" --only-show-errors
aws s3 cp "$work/$name.json" "s3://$BACKUP_BUCKET/sqlite/$name.json" \
  --region "$AWS_REGION" --sse AES256 --only-show-errors

install -d -m 700 /var/lib/mini-uptime-monitor
cp "$work/$name.json" /var/lib/mini-uptime-monitor/last-backup.json.tmp
mv /var/lib/mini-uptime-monitor/last-backup.json.tmp /var/lib/mini-uptime-monitor/last-backup.json
# Remove only this run's volume snapshot, after both S3 uploads succeeded.
docker exec mini-uptime-monitor-web-1 python -c \
  'import pathlib,sys; pathlib.Path(sys.argv[1]).unlink()' "/app/data/backups/$name"
echo "Backup uploaded: s3://$BACKUP_BUCKET/sqlite/$name sha256=$digest"
