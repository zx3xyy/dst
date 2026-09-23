# Operating the server

Run shell commands below on the Ubuntu host from `~/dst`. `scripts/docker.sh`
uses Docker directly or the user's already-authorized docker group. It does not
require passwords in scripts or grant new permissions.

## Status and joining

```bash
python3 scripts/serverctl.py status
bash scripts/docker.sh compose logs --tail=60
```

Check both `Master/server_log.txt` and `Caves/server_log.txt` under the cluster.
Look for online startup, cave readiness and no fatal mod errors. A client that
passes authentication has not necessarily finished loading; look for player
spawn/resume messages. A healthy container does not test outside connectivity.

On the same LAN, use the current server IP in the **game console** (`~`):

```lua
c_connect("192.0.2.10", 10999, "YOUR_ROOM_PASSWORD")
```

This is not a zsh/bash command. On this deployment the room is `YOUR_SERVER_NAME` and
Wi-Fi was `YOUR_WIFI_NAME`; verify current settings before relying on these names/IPs.
Friends on another network use the online room listing or the public address.
Test cave travel too. Public-IP connections from inside the LAN depend on NAT
loopback; ordinary TCP web port checkers do not test the game's UDP ports.

## Admins

Match display names to Klei IDs in `Client authenticated` log entries. Add only
players the owner selected:

```bash
python3 scripts/serverctl.py admins KU_FIRST_PLAYER KU_SECOND_PLAYER
```

This preserves other entries, writes private `adminlist.txt` inside the cluster,
and reloads both shards' permission lists. Players reconnect to refresh their
permissions. Verify after reconnecting:

```bash
python3 scripts/serverctl.py console 'for _,v in ipairs(TheNet:GetClientTable() or {}) do print(v.name, v.admin) end'
```

These are full admin privileges. The initial owner requested both PLAYER_ONE and
PLAYER_TWO; their actual IDs remain in the private cluster file and backups.
A new deployment needs that file restored or IDs supplied via `--admins-file`.

## Rollback

From the host:

```bash
python3 scripts/serverctl.py rollback 2
```

The command first creates a stable on-disk backup under `backups/pre-rollback/`,
then sends exactly one `c_rollback(2)` to Master using Supervisor's local stdin
RPC. No public management port is opened. If delivery or verification is unclear,
inspect the logs before retrying; another request can roll back further.

Verify `Received world rollback request`, the Master's chosen snapshot, and
`Synchronizing backward to master snapshot` plus cave readiness. Let the game's
rollback API choose the matching snapshots; do not independently delete save
files or assume that the target is latest-number minus the requested count.
Players reconnect after the reload.

An admin can instead stand on the **surface**, open `~`, switch to **Remote**
with Ctrl, then enter `c_rollback(2)` once. The direct in-game command does not
create the extra pre-rollback archive that the host helper creates. Built-in
rollback voting requires three yes votes in the installed version, so admins
are more convenient for the two-player group.

## Save, stop and restart

```bash
python3 scripts/serverctl.py save
```

Wait for the resulting world/user serialization messages. The command receipt
means delivery, not completion. Console commands are sent through the existing
Supervisor socket; the earlier assumption that no live console was available
was incorrect.

For shutdown, admins can use `c_shutdown(true)` in the game's remote console.
Because Supervisor restarts exited shards, also stop the container for a lasting
shutdown. When using the host, first save and verify completion, then:

```bash
bash scripts/docker.sh compose stop
# Later:
bash scripts/start.sh
```

Allow the configured shutdown grace period. An earlier startup hung on OS signals;
do not treat forced termination as a normal safe-save mechanism. Investigate
shutdown logs if stop does not finish. Avoid rebooting while a save is in progress.
Closing just the game client leaves the server online and pauses the world when
empty. Host reboot restores a previously running container; a manually stopped
container remains stopped until started explicitly.

## Backups and updates

`python3 scripts/snapshot.py` makes a verified backup of already-saved data without
stopping the game. It excludes the Klei token. See [Drive backups](drive-backups.md)
for the daily schedule and restore steps. Keep an independent token copy.
The older `scripts/backup.sh` is a stop/start full-data archive and may wait for
slow shutdown; prefer the snapshot method during play.

Game and six normal workshop mods update at startup. Moving Box is maintained as
a local legacy mod; `scripts/prepare-legacy-mod.py` reinstalls it on fresh setup
from Steam's official metadata/download URL. Existing copies are preserved.
Never drop a missing mod just to start: saved mod entities may be lost.

For image maintenance, save/back up first and choose a maintenance window:

```bash
bash scripts/docker.sh compose build --pull --no-cache
bash scripts/docker.sh compose up -d
```

Changing scripts inside the image requires rebuilding/recreating to take effect.
Do not recreate the running server just to inspect status or update documentation.

## Troubleshooting

- Steam `Missing configuration` or file-permission errors after copying runtime:
  inspect cache ownership. The entrypoint restores updater files to root ownership
  and retries metadata fetches. It preserves downloads.
- Slow first connection: distinguish mod downloads, world loading and network
  transfer. Get the client log rather than deleting mods on a healthy server.
- Mac client log: `~/Documents/Klei/DoNotStarveTogether/client_log.txt` (also check
  account subdirectories). Preserve before relaunching and store it in `incoming/`.
- Don't run two copies of the same cluster against the same save directory.
