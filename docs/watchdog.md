# Update watchdog

Enable on a running deployment in `~/dst`:

```sh
./setup.sh --watchdog
# Or install just the timer:
bash scripts/setup-watchdog.sh
```

The systemd user timer checks approximately every 30 minutes after each completed
check, starting five minutes after boot (or immediately if enabled later).
There is **no daily restart**. User lingering must be enabled to run after logout;
the current host already has it enabled. On another host, check with
`loginctl show-user "$USER" -p Linger` and enable with `loginctl enable-linger`.

The watchdog asks SteamCMD for app 343050's public build metadata and compares it
with the installed manifest. Checking metadata does not install game files.
A stopped server stays stopped. Unknown status, Steam errors, and unhealthy shard
processes fail the check without initiating a restart. Docker and Supervisor
retain their existing crash-restart behavior; this watchdog is for game updates,
not arbitrary crash recovery or standalone mod-update detection.

When a newer game build exists:

1. Query both shards for players, including clients still loading. If occupied,
   defer until the next check.
2. Temporarily close new connections on both shards and recheck player counts.
   A five-minute game-side lease reopens connections if preparation is interrupted.
3. Request saves with completion callbacks on both shards, then create and verify
   a local archive in `backups/pre-update/`. A backup failure aborts the update.
4. Recheck occupancy before shutdown. Save/shut down through the game console and
   shut down Supervisor. Docker's existing restart policy starts the updater.
5. If native shutdown hangs for 90 seconds, terminate the original game processes
   only after **both** fresh logs confirm world serialization, Lua closure, and
   final shutdown. Otherwise fail for operator review.
6. Allow up to 20 minutes for updates and world loading. Confirm the installed
   build, both Supervisor processes, lobby registration, shard connection, and
   fresh game-console responses.

Updates also run the existing startup mod updater. No mod is disabled or removed
by the watchdog. Pre-update backups are local, retained without automatic deletion;
the separate daily Drive job uploads archives from `backups/daily/`.

## Inspect and control

```sh
systemctl --user list-timers dst-watchdog.timer
systemctl --user status dst-watchdog.service
tail -60 runtime/logs/watchdog.log
python3 scripts/watchdog.py --check-only
# Run a normal check now (may update an empty outdated server):
systemctl --user start dst-watchdog.service
# Disable future checks:
systemctl --user disable --now dst-watchdog.timer
```

Disabling the timer does not cancel an update already underway. Let a running
update finish; do not interrupt it midway through shutdown or installation.

A file lock prevents overlapping watchdog runs. Before shutdown the watchdog
writes `runtime/watchdog/needs-review`. It clears this only after successful
readiness checks. An interrupted or failed update leaves this file in place,
blocking additional automatic attempts. Inspect the game/update logs, restore
normal readiness, then remove that file to allow checks again. Do not clear it
blindly or restore an old backup over a live world. Success details are recorded
in `runtime/watchdog/last-update.json`; all logs/state stay Git-ignored.

The unattended update path is covered by simulated failure/ordering tests. The
live installation check validates metadata and current status without forcing an
unnecessary restart or interrupting players.
