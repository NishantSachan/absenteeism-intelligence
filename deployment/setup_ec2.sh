#!/usr/bin/env bash
# setup_ec2.sh - install and start the FastAPI backend on an Ubuntu 24.04 EC2 server.
#
# Run ON THE SERVER from the unpacked release folder, as the normal 'ubuntu' user:
#       bash deployment/setup_ec2.sh
# Safe to run again. Dry run without sudo/systemd/nginx (used for off-server testing):  SKIP_SYSTEMD=1 bash deployment/setup_ec2.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE_NAME="absenteeism-api"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
RUN_USER="$(id -un)"
CONF_DIR=/etc/absenteeism

say() { printf '\n==> %s\n' "$*"; }

say "1/7 Checking the release files"
for f in backend/requirements.txt backend/app/main.py src/predict.py src/simulation.py models/absenteeism_pipeline.joblib \
         models/model_metadata.json models/metrics.json reports/app_assets/analytics.json reports/app_assets/model_grid.json \
         reports/app_assets/evaluation.json deployment/absenteeism-api.service.template deployment/nginx-absenteeism.conf.template; do
  [ -e "$APP_DIR/$f" ] || { echo "ERROR: missing $f in $APP_DIR (was the whole release archive unpacked?)"; exit 1; }
done
# The raw dataset contains health-related personal data and must NOT be on the server.
if ls "$APP_DIR"/data/raw/*.csv >/dev/null 2>&1; then
  echo "WARNING: a raw CSV is present in data/raw/. The API does not need it; delete it."
fi

if [ "$SKIP_SYSTEMD" != "1" ]; then
  say "2/7 Installing system packages"
  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip nginx curl
else
  say "2/7 (skipped: system packages, dry run)"
fi

say "3/7 Creating the Python environment and installing pinned runtime dependencies"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/backend/requirements.txt"

say "4/7 Offline smoke test: the saved model loads and predicts"
( cd "$APP_DIR" && .venv/bin/python deployment/smoke_check.py )

if [ "$SKIP_SYSTEMD" = "1" ]; then
  say "Dry run finished: swap, nginx and systemd steps were skipped."
  exit 0
fi

say "5/7 Adding a 1 GB swap file if none exists (protects a 1 GiB server from running out of memory)"
if [ "$(swapon --show --noheadings | wc -l)" -eq 0 ]; then
  sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
else
  echo "Swap already present, skipping."
fi

say "6/7 Origin secret and nginx"
sudo mkdir -p "$CONF_DIR"
if [ ! -f "$CONF_DIR/origin_secret" ]; then
  head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40 | sudo tee "$CONF_DIR/origin_secret" >/dev/null
  sudo chmod 600 "$CONF_DIR/origin_secret"
fi
SECRET="$(sudo cat "$CONF_DIR/origin_secret")"
sed -e "s|__ORIGIN_SECRET__|$SECRET|g" "$APP_DIR/deployment/nginx-absenteeism.conf.template" | sudo tee /etc/nginx/sites-available/absenteeism >/dev/null
sudo chmod 640 /etc/nginx/sites-available/absenteeism          # contains the origin secret: root only
sudo ln -sf /etc/nginx/sites-available/absenteeism /etc/nginx/sites-enabled/absenteeism
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx

say "7/7 Installing and starting the systemd service"
sed -e "s|__USER__|$RUN_USER|g" -e "s|__APP_DIR__|$APP_DIR|g" \
    "$APP_DIR/deployment/absenteeism-api.service.template" | sudo tee /etc/systemd/system/$SERVICE_NAME.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Waiting for the API to answer its health check..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1/health" >/dev/null 2>&1; then
    echo "API is up (health OK after ${i}s, directly and through nginx)."
    echo
    echo "NEXT: add this custom header to the CloudFront API origin (Origin settings > Add custom header):"
    echo "      Header name : X-Origin-Verify"
    echo "      Header value: $SECRET"
    exit 0
  fi
  sleep 1
done
echo "API did not become healthy in 30 s. Look at the logs:  sudo journalctl -u $SERVICE_NAME -n 80 --no-pager"
exit 1
