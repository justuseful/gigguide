#!/usr/bin/env bash
# Installs or updates the gig guide on an Ubuntu 24.04 box. Safe to re-run.
#   REPO_URL=https://github.com/<user>/gigguide.git sudo -E bash setup.sh
set -euo pipefail

: "${REPO_URL:?Set REPO_URL to the git repository URL}"
APP_DIR=/opt/gigguide/app
VENV=/opt/gigguide/venv
DATA_DIR=/var/lib/gigguide
ENV_FILE=/etc/gigguide.env

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv git nginx

# 1GB of swap makes a 1GB-RAM box far less likely to OOM during installs.
if ! swapon --show --noheadings | grep -q /swapfile; then
  fallocate -l 1G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Oracle's Ubuntu images ship iptables rules that reject everything except SSH, and they
# take effect before UFW's rules. Open the web ports (and alternate SSH port) persistently.
RULES=/etc/iptables/rules.v4
if [ -f "$RULES" ] && ! grep -q -- '--dports 80,443,2222' "$RULES"; then
  sed -i '0,/-A INPUT -j REJECT/s//-A INPUT -p tcp -m state --state NEW -m tcp -m multiport --dports 80,443,2222 -j ACCEPT\n&/' "$RULES"
  iptables-restore --test "$RULES"
fi
iptables -C INPUT -p tcp -m multiport --dports 80,443,2222 -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p tcp -m multiport --dports 80,443,2222 -j ACCEPT

id -u gigguide >/dev/null 2>&1 || useradd --system --home /opt/gigguide --shell /usr/sbin/nologin gigguide
mkdir -p /opt/gigguide "$DATA_DIR/uploads"

# Code stays root-owned (read-only for the service); only the data dir is writable.
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOF
SECRET_KEY=$(openssl rand -hex 32)
GIGGUIDE_ADMIN_USER=admin
GIGGUIDE_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
GIGGUIDE_DATA_DIR=$DATA_DIR
EOF
  chmod 600 "$ENV_FILE"
fi

# Create the database and starter venues (idempotent).
( set -a; . "$ENV_FILE"; set +a; cd "$APP_DIR" && "$VENV/bin/flask" --app wsgi seed )
chown -R gigguide:gigguide "$DATA_DIR"

install -m 644 "$APP_DIR/deploy/gigguide.service" /etc/systemd/system/gigguide.service
install -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/gigguide
ln -sf /etc/nginx/sites-available/gigguide /etc/nginx/sites-enabled/gigguide
rm -f /etc/nginx/sites-enabled/default

install -m 755 "$APP_DIR/deploy/backup.sh" /usr/local/bin/gigguide-backup
echo '15 3 * * * root /usr/local/bin/gigguide-backup' > /etc/cron.d/gigguide-backup

systemctl daemon-reload
systemctl enable gigguide >/dev/null
systemctl restart gigguide
nginx -t
systemctl reload nginx

echo "Deployed. Admin login is in $ENV_FILE (sudo cat $ENV_FILE)."
