# Don't Starve Together home server

A persistent surface + caves server, built locally on Ubuntu 24.04. Game updates
come from SteamCMD at startup. Saves, mods, credentials, downloads and backups
stay under this checkout and outside Git.

## Deploy or restore

Prerequisites: Linux x86_64, Python 3.11+, [Docker Engine with Compose](https://docs.docker.com/engine/install/ubuntu/), and Docker access for the current user.
The game UID/GID is 1000, matching this host's account. Keep this checkout at
`~/dst` if using the supplied backup timer and personal skill.

```bash
git clone git@github.com:zx3xyy/dst.git ~/dst
cd ~/dst
mkdir -p incoming
chmod 700 incoming
# Copy your world ZIP or backup tar.gz and a private cluster_token.txt into incoming/.
./setup.sh --archive incoming/Cluster_9.zip \
  --token-file incoming/cluster_token.txt --start --install-skill
```

To restore one of this project's backups, pass its `.tar.gz` instead of the ZIP.
Backups omit the Klei token; retain the token separately or generate a new one.
Both surface and caves are required. Setup refuses to overwrite an existing
cluster or silently generate a replacement world. To replace a deployment,
first save/stop it and retain the old cluster in `backups/` before importing.

For the existing deployment:

```bash
./setup.sh                     # Validate existing files; no restart
./setup.sh --build             # Rebuild image; no restart
./setup.sh --start             # Build and start/recreate; may interrupt players
python3 scripts/serverctl.py status
```

Add `--admins-file incoming/adminlist.txt` for a fresh setup. Put verified `KU_…`
Klei IDs one per line; see `config/admins.example.txt`. Restored admin lists are
preserved. Real account lists, room passwords and tokens are not checked in.

Initial installation can take time. Check `bash scripts/docker.sh compose logs
--tail=60`; a running container is not necessarily a ready world. Confirm both
shards load and connect before inviting players. See [operations](docs/operations.md).

## Operations

```bash
python3 scripts/serverctl.py status
python3 scripts/serverctl.py save
python3 scripts/serverctl.py rollback 2
python3 scripts/serverctl.py admins KU_FIRST_PLAYER KU_SECOND_PLAYER
```

Rollback takes a local backup first and sends **one** request to the surface;
the game synchronizes caves. Verify the logs instead of resending on disconnect.
Admins should reconnect after the permission list reload. They get full game
admin permissions, not only rollback access.

[Operations guide](docs/operations.md): joining, admin commands, saves, stopping,
reboot behavior, rollback verification, troubleshooting, and update procedures.
[Deployment notes](docs/deployment-notes.md): decisions and fixes from this setup.

## Daily Google Drive backups

```bash
./setup.sh --drive
```

This installs a checksum-verified rclone under `runtime/tools/`, asks for Google
authorization, uploads a test backup and verifies it, then enables the timer.
The schedule is **04:00 America/Los_Angeles**, destination **DST-Backups**.
Do not run with sudo. Authorization and a successful cloud test are required;
see [backup setup and restore](docs/drive-backups.md).

The daily job leaves the server running and captures stable, already-saved data,
not unsaved in-memory progress. No automatic version deletion is configured.

## Files and persistence

| Path | Purpose | In Git? |
|---|---|---|
| `setup.sh`, `scripts/`, `docker/`, `Dockerfile`, `compose.yaml` | Deployment and operations | Yes |
| `docs/`, `systemd/`, `skills/`, `tests/`, `config/` | Guides, timer, skill, checks, examples | Yes |
| `data/DoNotStarveTogether/Cluster_1/` | World, players, settings, local mods, token and admins | No |
| `runtime/game/`, `runtime/steamcmd/`, `runtime/steam-home/` | Game downloads and updater caches | No |
| `runtime/rclone/`, `runtime/tools/`, `runtime/logs/` | OAuth, tools and diagnostic logs | No |
| `incoming/`, `backups/` | Original uploads and backup archives | No |

Bind mounts survive container replacement and host reboot. Docker still keeps
its own images, container metadata and bounded console logs in its normal engine
storage. Do not delete `runtime/` to troubleshoot an update: partial downloads
are reusable. Save files use UID 1000; updater caches are root-owned because
Steam rejects certain files copied with the wrong ownership.

## Networking and boot

Reserve the server's LAN IP on the router. Forward UDP **10999**, **11000**,
**12346**, **12347** to the same ports on that IP. The internal shard port 10888
stays internal. Test from a different network and enter the caves as well.
On this host Docker is enabled at boot, automatic idle suspend is disabled, and
`unless-stopped` restarts an active container after a reboot. Verify those host
settings on a new machine; setup does not change them automatically.

## Validate changes

```bash
python3 -m unittest discover -s tests -v
bash -n setup.sh scripts/*.sh docker/*.sh
docker compose config --quiet
```

The personal `$dst-server` skill is sourced from `skills/dst-server/`. Install its
symlink with `./setup.sh --install-skill`; changes remain tracked in this repo.
