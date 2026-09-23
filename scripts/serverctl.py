#!/usr/bin/env python3
"""Operate the existing DST cluster through Supervisor's local stdin RPC."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
CLUSTER = ROOT / 'data/DoNotStarveTogether/Cluster_1'
RPC = '''import sys,xmlrpc.client
from supervisor.xmlrpc import SupervisorTransport
proxy=xmlrpc.client.ServerProxy('http://localhost',transport=SupervisorTransport(None,None,'unix:///var/run/supervisor.sock'))
proxy.supervisor.sendProcessStdin('dst-server:dst-server-'+sys.argv[1],sys.argv[2]+'\\n')
print('Command delivered to '+sys.argv[1]+'. Verify the game log before retrying.')
'''


def docker(*args):
    subprocess.run(['bash', str(ROOT / 'scripts/docker.sh'), *args], cwd=ROOT, check=True)


def send(shard, command):
    docker('compose', 'exec', '-T', 'server', 'python3', '-c', RPC, shard, command)


def add_admins(path, ids):
    if not ids or any(not re.fullmatch(r'KU_[A-Za-z0-9_-]+', uid) for uid in ids):
        raise ValueError('Supply verified Klei IDs beginning KU_, not player names.')
    lines = path.read_text().splitlines() if path.exists() else []
    for uid in ids:
        if uid not in lines:
            lines.append(uid)
    temporary = path.with_suffix('.tmp')
    temporary.write_text('\n'.join(lines) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('status')
    sub.add_parser('save')
    rollback = sub.add_parser('rollback', help='Back up saved data, then send ONE rollback request')
    rollback.add_argument('count', type=int)
    admins = sub.add_parser('admins')
    admins.add_argument('ids', nargs='+', help='Verified Klei IDs to add persistently')
    console = sub.add_parser('console')
    console.add_argument('command', help='Lua console code; quote as a single argument')
    console.add_argument('--shard', choices=['master', 'cave'], default='master')
    args = parser.parse_args()
    if args.action == 'status':
        docker('compose', 'ps')
        docker('compose', 'exec', '-T', 'server', 'supervisorctl', '-c', '/etc/supervisor/supervisor.conf', 'status')
    elif args.action == 'save':
        send('master', 'c_save()')
        print('Save requested; this receipt alone does not confirm save completion.')
    elif args.action == 'rollback':
        if not 1 <= args.count <= 20:
            parser.error('Rollback count must be between 1 and 20.')
        subprocess.run([sys.executable, str(ROOT/'scripts/snapshot.py'), '--output', str(ROOT/'backups/pre-rollback')], check=True)
        send('master', f'c_rollback({args.count})')
        print('Do NOT repeat just because clients disconnect. Verify rollback and cave synchronization in both shard logs.')
    elif args.action == 'admins':
        add_admins(CLUSTER / 'adminlist.txt', args.ids)
        for shard in ('master', 'cave'):
            send(shard, 'TheNet:LoadPermissionLists()')
        print('Admin list saved and reloaded. Players must reconnect; verify their admin flags after reconnecting.')
    else:
        send(args.shard, args.command)


if __name__ == '__main__':
    main()
