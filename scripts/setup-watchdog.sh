#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$PWD" == "$HOME/dst" ]] || { echo 'The supplied timer expects ~/dst.' >&2; exit 1; }
umask 077
mkdir -p runtime/logs runtime/watchdog "$HOME/.config/systemd/user"
# A read-only live check must pass before enabling unattended updates.
python3 scripts/watchdog.py --check-only
for unit in dst-watchdog.service dst-watchdog.timer; do
    target="$HOME/.config/systemd/user/$unit"
    if [[ -e "$target" || -L "$target" ]]; then
        [[ "$(readlink -f "$target")" == "$PWD/systemd/$unit" ]] || {
            echo "Refusing to overwrite unrelated unit: $target" >&2; exit 1;
        }
    else
        ln -s "$PWD/systemd/$unit" "$target"
    fi
done
systemctl --user daemon-reload
systemctl --user enable --now dst-watchdog.timer
systemctl --user list-timers dst-watchdog.timer --no-pager
