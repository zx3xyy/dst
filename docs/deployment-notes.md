# Deployment decisions and verified fixes

This file records decisions useful when redeploying, rather than a current-status
promise. Read live logs and configuration for the current version and players.

- Imported an existing surface+caves cluster from `Cluster_9.zip`, retaining
  world/player data, original password, settings and seven server mods. The ZIP
  stays private in `incoming/`; snapshot restores also preserve the admin list.
- Replaced the May 2022 Debian 10 community image with a local Ubuntu 24.04 build.
  The game itself is fetched from SteamCMD app 343050. The Docker image's age and
  the installed game version are separate concerns.
- Persisted game files, SteamCMD and its metadata under `runtime/`, as well as
  `/data`. A partial game download successfully resumed after image replacement.
- Copying cache files with host ownership caused Steam errors. Restoring updater
  ownership to root allowed the download to continue; gameplay data remains UID
  1000. The entrypoint encodes this fix.
- Moving Box (1079538195) stalled in Steam's normal Workshop updater. Steam's
  GetPublishedFileDetails API returned an official legacy ZIP, which was installed
  locally with Windows path separators normalized. The new setup automates this.
- Surface, caves, all seven mods, and player entry were verified. Both players
  travelled between shards. Room/IP information still needs checking on a new host.
- Supervisor's `sendProcessStdin` RPC accepts live game-console commands through
  the local Unix socket. A read-only print probe verified it before rollback.
- A requested `c_rollback(2)` was delivered once to Master. The engine chose
  snapshot 1330 and synchronized Caves to the same snapshot. A pre-rollback
  archive was retained. Use the engine API, not arithmetic on snapshot numbers.
- Both requested players were added to `adminlist.txt`; permission lists loaded
  successfully on both shards. Existing sessions initially kept their old flags,
  so players need to reconnect and have their permissions verified.
- Google Drive backup tooling targets 04:00 America/Los_Angeles, with local
  checksummed snapshots and remote checksum verification. Enabling it requires
  the user's OAuth authorization and a successful first upload. Check the timer
  and last-success marker instead of assuming authorization has been completed.

Repository source is sufficient to rebuild the software. It is intentionally
**not sufficient to recover your world or credentials**: transfer a private
cluster backup and token separately, plus Drive OAuth configuration if desired.
