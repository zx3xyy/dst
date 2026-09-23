#!/usr/bin/env bash
# Stops the server to make a consistent backup. Brief downtime is expected.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
running=$(docker compose ps --status running -q server)
resume() {
    if [[ -n "$running" ]]; then docker compose start server; fi
}
trap resume EXIT
docker compose stop server
archive="backups/dst-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$archive" data
echo "Backup saved: $archive"
