#!/usr/bin/env bash
# Nightly SQLite backup (consistent copy via the sqlite backup API), keeps 14 days.
set -euo pipefail
OUT=/var/lib/gigguide/backups
mkdir -p "$OUT"
/opt/gigguide/venv/bin/python - <<'PY'
import datetime, pathlib, sqlite3
src = sqlite3.connect("/var/lib/gigguide/gigguide.sqlite3")
dst = sqlite3.connect(pathlib.Path("/var/lib/gigguide/backups") / f"gigguide-{datetime.date.today():%Y%m%d}.sqlite3")
src.backup(dst)
dst.close()
src.close()
PY
find "$OUT" -name 'gigguide-*.sqlite3' -mtime +14 -delete
