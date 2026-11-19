#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${UBND_DATA_DIR:-/var/lib/ubnd-ai}"
BACKUP_ROOT="${UBND_BACKUP_DIR:-/var/backups/ubnd-ai}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
STAMP="$(date -u +%Y-%m-%d_%H%M%S)"
DEST_DIR="${BACKUP_ROOT}/${STAMP}"

mkdir -p "${DEST_DIR}/tenants"

python3 - "${DATA_DIR}" "${DEST_DIR}" <<'PY'
import pathlib
import sqlite3
import sys

data_dir = pathlib.Path(sys.argv[1])
dest_dir = pathlib.Path(sys.argv[2])

def online_backup(src_path: pathlib.Path, dst_path: pathlib.Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(src_path)) as src, sqlite3.connect(str(dst_path)) as dst:
        src.backup(dst)

root_db = data_dir / "ubnd_ai.db"
if root_db.is_file():
    online_backup(root_db, dest_dir / "ubnd_ai.db")

tenants_dir = data_dir / "tenants"
if tenants_dir.is_dir():
    for db_file in sorted(tenants_dir.glob("*.db")):
        online_backup(db_file, dest_dir / "tenants" / db_file.name)
PY

find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +
echo "[backup-sqlite] Completed online backup -> ${DEST_DIR}"

