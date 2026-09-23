# DST home server

Imported `incoming/Cluster_9.zip`: surface + caves, 7 workshop mods, original
world settings and password preserved, pause when empty enabled. All 100 save
data files matched the original ZIP after import. Docker access and Klei token
are present. DST version 747465 is installed; Klei authentication, surface
startup, cave startup, and the connection between shards have been verified.
The world pauses when empty. Player login and outside-in access need testing.
The original ZIP is retained. No replacement world has been generated.

Moving Box (1079538195) uses a legacy Workshop archive. Steam's normal updater
timed out for it. Its official Steam GetPublishedFileDetails download was
extracted into data/DoNotStarveTogether/Cluster_1/mods/workshop-1079538195,
preserving the original mod configuration. The metadata and ZIP are retained
under runtime/. Its ServerModSetup line is excluded to avoid repeated stalls;
the other six mods are updated normally. Keep this local mod folder with saves.
If re-importing from ZIP, preserve/reinstall this legacy mod before startup.

## Persistent files

`data/` stores world saves, cluster settings, token, and mods.
`runtime/game/` stores the downloaded dedicated server, including partial
Steam downloads. `runtime/steamcmd/` stores SteamCMD and its cache;
`runtime/steam-home/` stores Steam's root-user metadata and logs.
All are bind mounts outside the container and excluded from Git.
They survive a container restart, host reboot, or Compose container recreation.
Do not delete these directories when updating. Startup checks for updates,
but reuses installed files and resumable downloads instead of starting over.

## Import

Put the original archive in `incoming/`. Preserve an untouched copy there.
The image expects the complete cluster at
`data/DoNotStarveTogether/Cluster_1/`, including `cluster.ini`, `Master/`,
and (if used) `Caves/`. The compose file currently assumes surface + caves;
adapt the supervisor and preflight if the supplied world has no caves.
Inspect and adapt any cloud-save layout before starting.

Preserve world data, player data, world settings, and mod overrides.
Configure Master/Caves game ports as 10999/11000 and Steam master server
ports as 12346/12347 in their server.ini files. Shard communication should
use a shared internal port and key, with the master on loopback.
Configure separate Steam authentication ports if explicitly specified.
Add workshop IDs from modoverrides.lua to mods/dedicated_server_mods_setup.lua.
Set pause_when_empty = true in cluster.ini's GAMEPLAY section.

Store the Klei token in Cluster_1/cluster_token.txt, not in compose or chat.
The game runs as UID/GID 1000, matching the host account. Keep backups private
because they contain the token. Build and diagnostic logs go in runtime/logs/.
SteamCMD's runtime files are owned by container root: it rejects certain cache
files owned by a different UID. Leave that ownership intact; use sudo if these
runtime files need manual maintenance. World saves remain owned by UID 1000.

## Run (from this directory)

The account is now in the docker group. New login sessions can use Docker
directly; existing sessions can use `sg docker -c 'docker compose ps'`.
Alternatively use sudo:

```sh
sudo docker compose build --pull
sudo bash scripts/start.sh
sudo docker compose logs --tail=100 -f
sudo docker compose ps
sudo bash scripts/backup.sh
sudo docker compose stop
```

Only start after import and mod review. The startup script refuses to start
without both saved worlds, token, and the expected port configuration.
Use `scripts/start.sh` rather than directly running `compose up`.

Docker is already enabled at boot. `unless-stopped` restores a running
container after reboot and restarts it after failure; an explicitly stopped
container stays stopped. Supervisor restarts failed shard processes. A Docker
unhealthy status alone does not restart the container. Verify actual login,
surface/cave travel and an external player's connection after launch.

Updates download at container startup. For planned updates, make a backup,
then restart with `sudo docker compose restart`. No automatic update or backup
schedule is installed yet; choose a maintenance window after migration.
Game updates come directly from Valve SteamCMD (app 343050). They do not
require a new container image. The Dockerfile builds on Ubuntu 24.04;
to refresh its operating-system packages, run `docker compose build --pull
--no-cache` followed by `docker compose up -d`. Existing game files remain in
runtime/ and are reused. The old 2022 community image is no longer used.
The desktop AC idle action was verified as `nothing` (no automatic suspend).
Wired Ethernet is preferable for 24/7 use.

## Daily Google Drive backup

The backup scripts and a daily 04:00 America/Los_Angeles timer are prepared.
Run `bash scripts/setup-drive-backup.sh` once to authorize Google Drive. The
script verifies the first upload before enabling the timer. Local snapshot
creation and archive integrity checks have passed; cloud authorization and
upload verification are still pending. See [the backup guide](docs/drive-backups.md).
This scheduled method keeps the server running and captures already-saved
progress. It is separate from the older `scripts/backup.sh` stop/start backup.

## Router access

Current Wi-Fi: YOUR_WIFI_NAME. Gateway: 192.0.2.1. Server Wi-Fi address: 192.0.2.10.
Reserve this address in DHCP (or reserve the Ethernet address if switching).
Forward these UDP ports to the same ports at the reserved server address:
10999, 11000, 12346, 12347. Do not expose the internal shard port.
The user reports port forwarding is configured. Outside-in connectivity and
in-game cave travel still need a player test from a different network.

The repository tracks Dockerfile, docker/, compose.yaml, supervisor.conf,
scripts/, and this guide. data/, incoming/, backups/, runtime/, and .env
are Git-ignored. Docker itself still manages image layers, container metadata,
and its bounded console-log storage in Docker's standard system data directory.
