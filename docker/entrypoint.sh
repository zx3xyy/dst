#!/bin/bash
set -euo pipefail
cluster=/data/DoNotStarveTogether/Cluster_1
[[ -s "$cluster/cluster_token.txt" && -f "$cluster/cluster.ini" ]] || {
    echo 'Missing imported cluster or Klei token.' >&2
    exit 1
}
mkdir -p /opt/steamcmd /opt/dst_server
# SteamCMD rejects some cache files copied with a different owner's UID.
chown -R root:root /opt/steamcmd /opt/dst_server /root/Steam
if [[ ! -x /opt/steamcmd/steamcmd.sh ]]; then
    curl -fSL --retry 3 https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
        -o /tmp/steamcmd.tar.gz
    tar -xzf /tmp/steamcmd.tar.gz -C /opt/steamcmd
    rm /tmp/steamcmd.tar.gz
fi

# Keep the user's mod configuration outside Steam's installation directory.
if [[ -L /opt/dst_server/mods ]]; then
    rm /opt/dst_server/mods
fi
echo 'Checking DST updates with SteamCMD (existing downloads are reused)...'
updated=false
for attempt in 1 2 3; do
    if /opt/steamcmd/steamcmd.sh +@sSteamCmdForcePlatformType linux \
        +force_install_dir /opt/dst_server +login anonymous \
        +app_info_update 1 +app_update 343050 +quit; then
        updated=true
        break
    fi
    echo "Steam update attempt $attempt failed; retrying shortly..." >&2
    sleep 10
done
[[ "$updated" == true && -x /opt/dst_server/bin64/dontstarve_dedicated_server_nullrenderer_x64 ]] || exit 1

mkdir -p "$cluster/mods"
if [[ -d /opt/dst_server/mods ]]; then
    cp -an /opt/dst_server/mods/. "$cluster/mods/"
    rm -rf /opt/dst_server/mods
fi
ln -s "$cluster/mods" /opt/dst_server/mods
chown -R dst:dst /data
echo 'Updating workshop mods...'
for attempt in 1 2 3; do
    runuser -u dst -- env HOME=/data dontstarve_dedicated_server_nullrenderer \
        -persistent_storage_root /data -ugc_directory /data/ugc -cluster Cluster_1 -only_update_server_mods
    if python3 - "$cluster/mods/dedicated_server_mods_setup.lua" <<'PY'
from pathlib import Path
import re, sys
moddir = Path(sys.argv[1]).parent
ids = set(re.findall(r'ServerModSetup\("(\d+)"\)', Path(sys.argv[1]).read_text()))
for overrides in moddir.parent.glob('*/modoverrides.lua'):
    ids.update(re.findall(r'\["workshop-(\d+)"\]\s*=\s*\{', overrides.read_text()))
missing = [i for i in ids if not (Path('/data/ugc/content/322330') / i / 'modinfo.lua').is_file()
           and not (Path(sys.argv[1]).parent / ('workshop-' + i) / 'modinfo.lua').is_file()]
if missing:
    print('Mod downloads still missing:', ', '.join(missing))
sys.exit(bool(missing))
PY
    then
        break
    fi
    [[ "$attempt" != 3 ]] || exit 1
done
echo 'Starting imported surface and caves...'
exec supervisord -c /etc/supervisor/supervisor.conf -n
