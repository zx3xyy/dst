#!/bin/bash
set -euo pipefail
cluster=/data/DoNotStarveTogether/Cluster_1
[[ -s "$cluster/cluster_token.txt" && -f "$cluster/cluster.ini" ]] || {
    echo 'Missing imported cluster or Klei token.' >&2
    exit 1
}
mkdir -p /opt/steamcmd /opt/dst_server
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
    if /opt/steamcmd/steamcmd.sh +force_install_dir /opt/dst_server \
        +login anonymous +app_update 343050 +quit; then
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
runuser -u dst -- env HOME=/data dontstarve_dedicated_server_nullrenderer \
    -persistent_storage_root /data -ugc_directory /data/ugc -cluster Cluster_1 -only_update_server_mods
echo 'Starting imported surface and caves...'
exec supervisord -c /etc/supervisor/supervisor.conf -n
