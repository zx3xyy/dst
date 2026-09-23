#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p runtime/rclone runtime/logs
export RCLONE_CONFIG="$PWD/runtime/rclone/rclone.conf"
rclone="$PWD/runtime/tools/rclone"
[[ -x "$rclone" ]] || { echo 'Missing runtime/tools/rclone.' >&2; exit 1; }
if [[ ! -e "$RCLONE_CONFIG" ]]; then
    printf '[dst-drive]\ntype = drive\nscope = drive.file\n' > "$RCLONE_CONFIG"
fi
chmod 600 "$RCLONE_CONFIG"
if ! "$rclone" lsf dst-drive: --max-depth 1 >/dev/null 2>&1; then
    echo 'Sign in to Google Drive. The scope only covers files created by this backup app.'
    echo 'If asked about a Shared Drive, answer no for a personal Drive.'
    echo 'Use a browser on this Ubuntu computer, or follow rclone headless authorization instructions.'
    "$rclone" config reconnect dst-drive:
fi
echo 'Creating and verifying the first backup before enabling the daily schedule...'
bash scripts/drive-backup.sh
mkdir -p "$HOME/.config/systemd/user"
for unit in dst-drive-backup.service dst-drive-backup.timer; do
    target="$HOME/.config/systemd/user/$unit"
    if [[ -e "$target" || -L "$target" ]]; then
        [[ "$(readlink -f "$target")" == "$PWD/systemd/$unit" ]] || {
            echo "Refusing to overwrite an unrelated unit: $target" >&2; exit 1;
        }
    else
        ln -s "$PWD/systemd/$unit" "$target"
    fi
done
systemctl --user daemon-reload
systemctl --user enable --now dst-drive-backup.timer
systemctl --user list-timers dst-drive-backup.timer --no-pager
