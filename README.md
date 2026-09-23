# DST home server

Prepared deployment; not running yet. Waiting for the original world, Klei
cluster token, and Docker access. No new world has been generated.

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
The image changes ownership of data on startup; subsequent host operations
may require sudo. Keep backups private because they contain the token.

## Run (from this directory)

Docker currently requires sudo for this account:

```sh
sudo docker compose pull
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
Ensure the host does not suspend. Wired Ethernet is preferable for 24/7 use.

## Router

Current gateway: 192.0.2.1. Current server Wi-Fi address: 192.0.2.10.
Reserve this address in DHCP (or reserve the Ethernet address if switching).
Forward these UDP ports to the same ports at the reserved server address:
10999, 11000, 12346, 12347. Do not expose the internal shard port.
Router model and WAN address still need checking for upstream/double NAT.
Firewall and outside-in connectivity have not been verified.

Image documentation: https://github.com/Jamesits/docker-dst-server
