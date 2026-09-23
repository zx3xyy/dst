# Daily Google Drive backups

Schedule: daily at **04:00 America/Los_Angeles**, following daylight saving time.
Destination: the private `DST-Backups` folder created in the authorized Drive.
Local archives: `~/dst/backups/daily/`. All versions are retained; no automatic
deletion or remote sync deletion is configured.

## One-time authorization and activation

Run on the Ubuntu host, without sudo:

```sh
cd ~/dst
bash scripts/setup-drive-backup.sh
```

This uses the SHA256-verified rclone binary in `runtime/tools/rclone`. The OAuth
configuration stays in `runtime/rclone/rclone.conf` with private permissions,
outside Git. Only `drive.file` access (files created by this app) is requested.
The setup performs a real backup/upload/check before enabling the timer.
Until authorization and that check succeed, the schedule is **not enabled**.

Use the browser on the Ubuntu machine for local authentication. If configuring
over SSH from another computer, follow rclone's headless login prompts (or use an
SSH tunnel for its localhost callback); the localhost URL refers to the server.
See https://rclone.org/remote_setup/ . Do not paste OAuth tokens into chat.

Rclone's shared Google client ID is being retired during 2026. If it is unavailable,
create a Google OAuth **Desktop app** client with Drive API enabled using
https://rclone.org/drive/#making-your-own-client-id . Use rclone's interactive
configuration to supply the client ID and secret in the private config:

```sh
runtime/tools/rclone --config runtime/rclone/rclone.conf config
```

Edit `dst-drive`, retain scope `drive.file`, then rerun the setup script. For an
external OAuth app, follow Google's publishing requirements for durable refresh
tokens; testing-mode credentials can expire. Do not commit OAuth credentials.

## What is backed up

The complete cluster includes surface/cave saves, player saves, settings and
local mods (including Moving Box). Logs, temporary files and `cluster_token.txt`
are excluded. On restoration, retain or regenerate the Klei token separately.
Room settings may contain the game password, so keep the Drive folder private.

The scheduled job does **not stop the server or force a game save**. It archives
the latest already-saved data. It waits for a quiet interval, checks hashes before
and after archiving, verifies archive contents and retries if files change. This
is a stable filesystem copy, not an atomic application checkpoint of both shards
or unsaved in-memory progress. Use an admin game save or graceful shutdown for a
specific up-to-the-second checkpoint.

Each archive contains a SHA256 manifest. Uploads use checksums and immutable
filenames; `rclone check` verifies the remote copy. Missed archives are retried
on later runs. A failed upload leaves the local archive intact and fails the job.

## Status and manual run

```sh
systemctl --user list-timers dst-drive-backup.timer
systemctl --user status dst-drive-backup.service
cat runtime/logs/drive-backup-last-success.txt
tail -60 runtime/logs/drive-backup.log
bash scripts/drive-backup.sh
```

Units live in `~/dst/systemd/` with symlinks in the user systemd directory.
User lingering is enabled on this host, allowing jobs after logout and reboot.
The persistent timer catches up a missed run after the machine returns.
To disable the schedule: `systemctl --user disable --now dst-drive-backup.timer`.

To restore, first stop/save the live world and retain a backup of its current
cluster. Inspect the archive and manifest, restore `Cluster_1` under
`data/DoNotStarveTogether/`, restore the token separately, and run the existing
startup checks. Never restore over a running world.
