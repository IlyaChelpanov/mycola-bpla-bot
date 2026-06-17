#!/usr/bin/env bash
# One-shot deploy for a Debian/Ubuntu VM (e.g. GCP e2-micro).
# Run AFTER creating $HOME/mycola-bpla-bot/.env with your keys.
set -euo pipefail

REPO="https://github.com/IlyaChelpanov/mycola-bpla-bot.git"
DIR="$HOME/mycola-bpla-bot"

echo ">> Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git

echo ">> Fetching code..."
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q origin main && git -C "$DIR" reset -q --hard origin/main
elif [ -d "$DIR" ]; then
  # Dir exists (holds your .env) but is not a repo yet — init in place.
  # .env is gitignored, so the checkout never touches it.
  git -C "$DIR" init -q
  git -C "$DIR" remote add origin "$REPO" 2>/dev/null || true
  git -C "$DIR" fetch -q origin main
  git -C "$DIR" reset -q --hard origin/main
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f "$DIR/.env" ]; then
  echo "ERROR: $DIR/.env not found. Create it first (see .env.example), then re-run." >&2
  exit 1
fi

echo ">> Python venv + deps..."
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt -q

echo ">> Installing systemd service..."
sudo cp deploy/mycola-bot.service /etc/systemd/system/mycola-bot.service
sudo sed -i "s|__USER__|$USER|g; s|__DIR__|$DIR|g" /etc/systemd/system/mycola-bot.service
sudo systemctl daemon-reload
sudo systemctl enable mycola-bot
sudo systemctl restart mycola-bot

sleep 4
echo ">> Status:"
sudo systemctl status mycola-bot --no-pager || true
echo
echo ">> Done. Live logs:  journalctl -u mycola-bot -f"
