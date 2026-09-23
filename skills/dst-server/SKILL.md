---
name: dst-server
description: Operate the user's persistent Don't Starve Together Docker server in ~/dst. Use for starting, stopping, reboot recovery, save locations, backups, updates, download status, or diagnosing connections and mods on this deployment.
---

# DST home server

Work in `~/dst` (`~/dst` for this user). Read the repository's
`README.md`, `compose.yaml`, and relevant scripts before changing the deployment.
Treat the live configuration and logs as authoritative; recorded versions,
addresses, and readiness statements can become stale.

Keep code and this skill's source in this Git repository. Keep world saves,
credentials, uploaded archives, downloaded software, caches, and diagnostic logs
under the project's Git-ignored directories. Never copy a token or room password
into skill instructions, tracked files, or diagnostic output. Docker's own image
layers and container metadata remain in its normal engine-managed storage.

## Routine operations

These commands belong in the **Ubuntu host terminal**, from `~/dst`.
Use `docker` directly if available. If the login session has not picked up the
user's docker-group membership, use `sg docker -c 'COMMAND'` as below.

```bash
cd ~/dst
# Status (read-only)
sg docker -c 'docker compose ps'
sg docker -c 'docker compose logs --tail=60'
# Start with existing-world checks
sg docker -c 'bash scripts/start.sh'
# Stop; read the save guidance below first
sg docker -c 'docker compose stop'
# Consistent on-disk backup, with a brief stop and restoration of prior running state
sg docker -c 'bash scripts/backup.sh'
```

Do not run start, stop, or backup commands just to answer a status or instructions
question. Inspect logs for secrets before quoting them to the user.

Closing the game client leaves the dedicated server running. The imported cluster
uses `pause_when_empty = true`; check that setting when answering about world time.
With Docker enabled at boot and `restart: unless-stopped`, a running container
returns after a host reboot. An explicitly stopped container stays stopped until
started again. Verify these settings instead of assuming they are unchanged.
An `unhealthy` Docker status does not itself trigger automatic restart.

## Saves and safe shutdown

- Whole cluster: `data/DoNotStarveTogether/Cluster_1/`.
- Surface and player data: `Master/save/` within the cluster.
- Caves: `Caves/save/` within the cluster.
- Settings, token, and local mods are also in the cluster; preserve them together.
- Original migration archive: `incoming/Cluster_9.zip` (verify it still exists).
- Backups: `backups/`; backups contain credentials and should stay private.

For a live world with recent player progress, have an administrator save using
`c_save()` in the game's **remote console**, or gracefully shut down using
`c_shutdown(true)`, before stopping the container. These are Lua game-console
commands, not shell commands. Do not assume the connected player is an admin just
because they own this computer; cluster-token ownership and player identity can
be different. Do not restart or reconfigure the world solely to explain shutdown.

An earlier deployment did not exit promptly on OS signals. Do not promise that
`docker compose stop` always saves the latest player progress. Inspect shutdown
and save logs, allow the configured grace period, and report a stuck shutdown.
Avoid forced termination of a live world as a routine workaround. The backup
script captures the files after stopping, but cannot recover unsaved progress if
the stop ultimately force-kills the process. Never restore the original ZIP over
newer player progress without a specific restoration request and retained backup.

## Persistence and updates

Bind mounts keep the following outside the container:

| Project path | Container path / purpose |
|---|---|
| `data/` | `/data`: saves, configuration, mods, user Steam data |
| `runtime/game/` | `/opt/dst_server`: installed game and partial downloads |
| `runtime/steamcmd/` | `/opt/steamcmd`: SteamCMD and cache |
| `runtime/steam-home/` | `/root/Steam`: updater metadata and logs |
| `runtime/logs/` | Host-side build and diagnostic artifacts |

Container restarts, host reboots, and container recreation reuse these files.
Do not erase runtime directories or recreate an unmounted container to fix a
slow download. World data is UID/GID 1000. SteamCMD runs as root and may reject
cache files copied with another owner; inspect ownership on metadata/permission
errors. The entrypoint restores root ownership for updater directories.

The image is built locally from `Dockerfile` on Ubuntu 24.04, not the old
`jamesits/dst-server` image. `docker/entrypoint.sh` checks game updates through
SteamCMD app 343050 at startup, then updates workshop mods. Startup checks are
not continuous automatic updates. No scheduled update/backup job was installed
as part of the initial deployment; inspect timers before claiming otherwise.

For a requested game update, save/backup first, then restart. For requested OS
image maintenance, build with `docker compose build --pull --no-cache` and
recreate with `docker compose up -d`; account for downtime and players.

Moving Box (`1079538195`) is a special case: its legacy archive was obtained from
Steam's official GetPublishedFileDetails file URL and extracted to
`data/DoNotStarveTogether/Cluster_1/mods/workshop-1079538195/`.
Its `ServerModSetup` line is excluded to avoid the observed legacy download stall;
its `modoverrides.lua` settings remain enabled. Preserve this directory. Metadata
and the ZIP are under `runtime/`. The other six mods use the normal updater.
Do not disable a missing mod to rush startup: saved mod entities can disappear.

## Readiness and connection troubleshooting

Distinguish image build, game download, verification, mod download, world startup,
and actual player entry. Report live progress and timestamp-based estimates,
not earlier percentages. Process health alone does not prove the world is playable.
Confirm both shard logs show online startup, caves link to the master, and no
fatal mod errors. A client authenticated message is not proof of completed loading.

Historically the host used Wi-Fi `YOUR_WIFI_NAME`, IP `192.0.2.10`, and gateway `192.0.2.1`.
Verify addresses before instructing users. UDP ports are 10999 (surface), 11000
(caves), and 12346/12347 (Steam). Do not expose the internal shard port 10888.
The user reported router forwarding was configured; do not equate that report
with a successful external test.

A local player can enter this in DST's console (the `~` key), substituting the
current IP and their existing password:

```lua
c_connect("192.0.2.10", 10999, "YOUR_EXISTING_PASSWORD")
```

Remote friends do not need the same Wi-Fi. Test the online room (historically
`YOUR_SERVER_NAME`) from another network, then enter the caves. Testing the public IP
from inside the home network can fail due to NAT loopback; TCP web port checkers
do not establish DST UDP reachability.

For client freezes, inspect server logs first. If authentication succeeds but
loading stops, ask for the client's screenshot and `client_log.txt`, saved before
relaunching. On Mac the documented location is
`~/Documents/Klei/DoNotStarveTogether/client_log.txt`; account subdirectories may
also need checking. Keep collected client logs in `incoming/` or `runtime/logs/`.
Do not alter a healthy server or remove world mods without evidence of the cause.
