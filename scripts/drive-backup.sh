#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p runtime/logs runtime/rclone backups/daily
exec 9>runtime/drive-backup.lock
flock -n 9 || { echo 'A backup is already running.'; exit 0; }
rclone="$PWD/runtime/tools/rclone"
export RCLONE_CONFIG="$PWD/runtime/rclone/rclone.conf"
[[ -x "$rclone" && -s "$RCLONE_CONFIG" ]] || {
    echo 'Google Drive not configured; run bash scripts/setup-drive-backup.sh.' >&2
    exit 1
}
# Fail before making a new archive if authorization is not usable.
"$rclone" lsf dst-drive: --max-depth 1 >/dev/null
python3 scripts/snapshot.py
# Retry all local daily archives, including uploads missed on previous nights.
"$rclone" copy backups/daily dst-drive:DST-Backups --include 'dst-*.tar.gz' \
    --checksum --immutable --retries 3 --contimeout 30s --timeout 5m
"$rclone" check backups/daily dst-drive:DST-Backups --include 'dst-*.tar.gz' --one-way
date -u '+Last verified upload: %Y-%m-%dT%H:%M:%SZ' > runtime/logs/drive-backup-last-success.txt
cat runtime/logs/drive-backup-last-success.txt
