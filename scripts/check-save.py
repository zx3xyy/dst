#!/usr/bin/env python3
"""Refuse to launch until the imported world and networking are ready."""
import configparser
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
cluster = root / 'data/DoNotStarveTogether/Cluster_1'
errors = []
if not (cluster / 'cluster.ini').is_file():
    errors.append('Missing imported Cluster_1/cluster.ini.')
token = cluster / 'cluster_token.txt'
if not token.is_file() or not token.read_text().strip():
    errors.append('Missing Klei token in Cluster_1/cluster_token.txt.')
for shard, port, steam_port in [('Master', 10999, 12346), ('Caves', 11000, 12347)]:
    ini = configparser.ConfigParser()
    try:
        ini.read(cluster / shard / 'server.ini')
        if ini.getint('NETWORK', 'server_port', fallback=0) != port:
            errors.append(f'{shard}/server.ini: NETWORK server_port must be {port}.')
        if ini.getint('STEAM', 'master_server_port', fallback=0) != steam_port:
            errors.append(f'{shard}/server.ini: STEAM master_server_port must be {steam_port}.')
    except (configparser.Error, ValueError) as exc:
        errors.append(f'{shard}/server.ini is invalid: {exc}')
    session = cluster / shard / 'save/session'
    if not session.is_dir() or not any(p.is_file() for p in session.rglob('*')):
        errors.append(f'Missing imported {shard}/save/session data. Do not generate a replacement world.')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print('Imported world and port checks passed. Token validity requires online verification.')
