#!/usr/bin/env python3
"""Prepare or deploy an existing DST world; never overwrite an existing cluster."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
CLUSTER=ROOT/'data/DoNotStarveTogether/Cluster_1'


def run(*args): subprocess.run(args,cwd=ROOT,check=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,help='Original cluster ZIP or our snapshot tar.gz; fresh deployment only')
    p.add_argument('--token-file',type=Path,help='Private cluster_token.txt; required for token-free backups')
    p.add_argument('--admins-file',type=Path,help='Klei IDs, one per line; adds to existing admins')
    p.add_argument('--build',action='store_true',help='Build current image without restarting the game')
    p.add_argument('--start',action='store_true',help='Build and start/recreate the server (may interrupt players)')
    p.add_argument('--drive',action='store_true',help='Install rclone and run interactive Drive backup setup')
    p.add_argument('--install-skill',action='store_true',help='Link repo skill into the user skill directory')
    args=p.parse_args()
    if sys.version_info<(3,11): p.error('Python 3.11+ is required.')
    if not shutil.which('docker'): p.error('Install Docker Engine and its Compose plugin first; see README.')
    run('bash','scripts/docker.sh','compose','version')
    for name in ('incoming','backups','runtime','runtime/game','runtime/steamcmd','runtime/steam-home','runtime/logs','runtime/rclone','data'):
        (ROOT/name).mkdir(parents=True,exist_ok=True,mode=0o700)
    if args.archive:
        command=[sys.executable,'scripts/import-save.py',str(args.archive.resolve())]
        if args.token_file: command+=['--token-file',str(args.token_file.resolve())]
        run(*command)
    elif not CLUSTER.exists():
        p.error('No cluster found. Supply --archive and --token-file; no new world will be generated.')
    elif args.token_file:
        token=CLUSTER/'cluster_token.txt'
        if token.exists() and token.read_bytes()!=args.token_file.read_bytes():
            p.error('Existing token differs. Replace it explicitly during a planned maintenance window.')
        if not token.exists(): shutil.copyfile(args.token_file,token);token.chmod(0o600)
    if args.admins_file:
        spec=importlib.util.spec_from_file_location('serverctl',ROOT/'scripts/serverctl.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        ids=[line.strip() for line in args.admins_file.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
        module.add_admins(CLUSTER/'adminlist.txt',ids)
        print('Admin configuration saved. For a running server use serverctl.py admins to reload now.')
    run(sys.executable,'scripts/prepare-legacy-mod.py')
    run(sys.executable,'scripts/check-save.py')
    run('bash','scripts/docker.sh','compose','config','--quiet')
    if args.build or args.start: run('bash','scripts/docker.sh','compose','build')
    if args.start: run('bash','scripts/start.sh')
    if args.install_skill:
        folder=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'
        folder.mkdir(parents=True,exist_ok=True)
        link=folder/'dst-server';source=ROOT/'skills/dst-server'
        if link.exists() or link.is_symlink():
            if link.resolve()!=source: p.error('Existing dst-server skill points elsewhere; not replacing it.')
        else: link.symlink_to(source)
    if args.drive:
        if ROOT!=Path.home()/'dst': p.error('Drive timer currently expects this checkout at ~/dst.')
        run(sys.executable,'scripts/install-rclone.py')
        run('bash','scripts/setup-drive-backup.sh')
    print('Setup checks passed. Use scripts/serverctl.py status for live readiness.')
    if not args.start: print('No server restart was requested.')


if __name__=='__main__': main()
