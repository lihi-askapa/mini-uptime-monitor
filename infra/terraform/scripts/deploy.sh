#!/usr/bin/env bash
# Embedded in the SSM document. Executed as root, not installed on the host.
set -euo pipefail

if [[ ! ${SSM_ImageTag:-} =~ ^[0-9a-f]{40}$ ]]; then
  echo "ImageTag must be a full 40-character lowercase commit SHA." >&2
  exit 2
fi

export AWS_REGION=eu-north-1
export AWS_DEFAULT_REGION=eu-north-1
readonly registry=944464821297.dkr.ecr.eu-north-1.amazonaws.com
export APP_IMAGE="$registry/mini-uptime-monitor:$SSM_ImageTag"
export DEMO_DOMAIN=pulse-13-60-191-46.sslip.io

exec 9>/var/lock/mini-uptime-monitor-deploy.lock
flock -n 9 || { echo "Another deployment is running." >&2; exit 1; }
cd /home/ec2-user/mini-uptime-monitor

compose=(docker compose -f compose.yaml -f compose.public.yaml -f compose.ecr.yaml --profile monitoring)
"${compose[@]}" config --quiet

# These files record a recovery reference, not an automatic rollback.
install -d -m 700 /var/lib/mini-uptime-monitor
previous_web=$(docker inspect --format '{{.Config.Image}}' mini-uptime-monitor-web-1)
previous_scheduler=$(docker inspect --format '{{.Config.Image}}' mini-uptime-monitor-scheduler-1)
if [[ "$previous_web" != "$previous_scheduler" ]]; then
  echo "Web and scheduler currently use different images; investigate before deploying." >&2
  exit 1
fi

# Isolate temporary registry credentials from root's normal Docker login.
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
aws ecr get-login-password --region "$AWS_REGION" |
  docker login --username AWS --password-stdin "$registry"
docker pull "$APP_IMAGE"

# Detect an existing deployment that needs recovery without overwriting its reference.
if [[ "$previous_web" != "$APP_IMAGE" ]]; then
  printf '%s\n' "$previous_web" > /var/lib/mini-uptime-monitor/previous-image.tmp
  mv /var/lib/mini-uptime-monitor/previous-image.tmp /var/lib/mini-uptime-monitor/previous-image
fi
echo "Requested image: $APP_IMAGE"
echo "Image before deployment: $previous_web"
deployment_started=$(date +%s)
"${compose[@]}" up -d --no-build --pull never

# Check image content IDs, rather than only the image names on containers.
expected_id=$(docker image inspect --format '{{.Id}}' "$APP_IMAGE")
for container in mini-uptime-monitor-web-1 mini-uptime-monitor-scheduler-1; do
  actual_id=$(docker inspect --format '{{.Image}}' "$container")
  [[ "$actual_id" == "$expected_id" ]] || { echo "Wrong image on $container" >&2; exit 1; }
done

# A deployment to the same image must still prove a new round completes.
# Public endpoints cover DNS, TLS and Caddy; SQLite proves fresh worker activity.
for attempt in {1..36}; do
  if curl --fail --silent --show-error --max-time 5 "https://$DEMO_DOMAIN/health" >/dev/null &&
     curl --fail --silent --show-error --max-time 5 "https://$DEMO_DOMAIN/health/monitoring" >/dev/null &&
     docker exec -i mini-uptime-monitor-web-1 python - "$deployment_started" <<'PY'
import os
import sqlite3
import sys
with sqlite3.connect(os.environ["DATABASE_PATH"], timeout=2) as db:
    row = db.execute("SELECT completed_at FROM monitor_state WHERE id=1").fetchone()
sys.exit(0 if row and row[0] > float(sys.argv[1]) else 1)
PY
  then
    printf '%s\n' "$APP_IMAGE" > /var/lib/mini-uptime-monitor/current-image.tmp
    mv /var/lib/mini-uptime-monitor/current-image.tmp /var/lib/mini-uptime-monitor/current-image
    echo "Deployment verified: both services use the requested image and a new scheduled round completed."
    exit 0
  fi
  sleep 5
done

echo "Deployment checks failed. No automatic rollback was attempted." >&2
echo "Inspect service logs; previous-image is the recovery reference if the image changed." >&2
exit 1
