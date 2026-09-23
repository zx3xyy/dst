#!/usr/bin/env python3
"""Atomically import one existing surface+caves cluster from ZIP or tar.gz."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def safe_path(name):
    p = PurePosixPath(name.replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or (p.parts and ':' in p.parts[0]):
        raise ValueError('Unsafe archive path')
    return p


def import_save(source, target, token_file=None):
    if target.exists():
        raise ValueError('Target exists; refusing to overwrite the deployed world.')
    if token_file and not token_file.read_text().strip():
        raise ValueError('Token file is empty.')
    archive = zipfile.ZipFile(source) if zipfile.is_zipfile(source) else tarfile.open(source, 'r:*')
    with archive:
        entries = []
        for entry in archive.infolist() if isinstance(archive, zipfile.ZipFile) else archive.getmembers():
            iszip = isinstance(archive, zipfile.ZipFile)
            path = safe_path(entry.filename if iszip else entry.name)
            if (iszip and stat.S_ISLNK(entry.external_attr >> 16)) or (not iszip and not (entry.isfile() or entry.isdir())):
                raise ValueError('Links and special files are not accepted.')
            if (entry.is_dir() if iszip else entry.isdir()):
                continue
            if any(p == '__MACOSX' or p == '.DS_Store' or p.startswith('._') for p in path.parts):
                continue
            entries.append((entry, path, entry.file_size if iszip else entry.size))
        roots = [p.parent for _, p, _ in entries if p.name == 'cluster.ini']
        if len(roots) != 1:
            raise ValueError('Expected exactly one cluster.ini in archive.')
        prefix = roots[0]
        files = [(e, p.relative_to(prefix), size) for e, p, size in entries if p.is_relative_to(prefix)]
        if sum(size for _, _, size in files) > 2 * 1024**3:
            raise ValueError('Archive exceeds 2 GiB; inspect before importing.')
        if len({p for _, p, _ in files}) != len(files):
            raise ValueError('Duplicate archive paths.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.import-', dir=target.parent) as tmp:
            staged = Path(tmp) / 'Cluster_1'
            staged.mkdir()
            for entry, relative, _ in files:
                path = staged / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) if isinstance(archive, zipfile.ZipFile) else archive.extractfile(entry) as stream:
                    with path.open('wb') as out:
                        shutil.copyfileobj(stream, out)
            manifests = [entry for entry, path, _ in entries if str(path) == 'backup-manifest.json']
            if manifests:
                entry = manifests[0]
                with archive.open(entry) if isinstance(archive, zipfile.ZipFile) else archive.extractfile(entry) as stream:
                    expected = json.load(stream)['files']
                for relative, record in expected.items():
                    path = staged / safe_path(relative)
                    with path.open('rb') as f:
                        if hashlib.file_digest(f, 'sha256').hexdigest() != record['sha256']:
                            raise ValueError(f'Backup checksum mismatch: {relative}')
            if token_file:
                shutil.copyfile(token_file, staged / 'cluster_token.txt')
            token = staged / 'cluster_token.txt'
            if not token.is_file() or not token.read_text().strip():
                raise ValueError('Supply --token-file; archive has no token.')
            token.chmod(0o600)
            for shard in ('Master', 'Caves'):
                if not any(p.is_file() for p in (staged/shard/'save/session').rglob('*')):
                    raise ValueError(f'Missing {shard} save data; refusing to generate a world.')
            def edit(path, changes):
                ini = configparser.ConfigParser(interpolation=None)
                ini.read(path, encoding='utf-8-sig')
                for section, values in changes.items():
                    if not ini.has_section(section): ini.add_section(section)
                    for key, value in values.items(): ini.set(section, key, str(value))
                with path.open('w') as f: ini.write(f)
            edit(staged/'cluster.ini', {'GAMEPLAY': {'pause_when_empty': 'true'}})
            mods = set()
            for shard, port, steam, auth in [('Master',10999,12346,8766), ('Caves',11000,12347,8767)]:
                edit(staged/shard/'server.ini', {'NETWORK': {'server_port': port}, 'STEAM': {'master_server_port': steam, 'authentication_port': auth}})
                f = staged/shard/'modoverrides.lua'
                if f.exists(): mods.update(re.findall(r'\["workshop-(\d+)"\]\s*=\s*\{', f.read_text()))
            moddir=staged/'mods'; moddir.mkdir(exist_ok=True)
            (moddir/'dedicated_server_mods_setup.lua').write_text(''.join(f'ServerModSetup("{m}")\n' for m in sorted(mods)))
            staged.rename(target)
    print('Imported existing world. Archive SHA256:', hashlib.sha256(source.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--destination', type=Path, default=ROOT/'data/DoNotStarveTogether/Cluster_1')
    args=parser.parse_args()
    token=args.token_file
    if token is None and (ROOT/'incoming/cluster_token.txt').exists(): token=ROOT/'incoming/cluster_token.txt'
    import_save(args.archive, args.destination, token)
