#!/usr/bin/env python3
"""Back up stable on-disk cluster files without stopping the running game."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time

ROOT = Path(__file__).resolve().parent.parent


def inventory(cluster):
    result = {}
    for path in sorted(cluster.rglob('*')):
        rel = path.relative_to(cluster)
        if any(part in {'server_temp', '.DS_Store'} for part in rel.parts):
            continue
        if path.name == 'cluster_token.txt' or path.name.endswith(('.log', '.lock')):
            continue
        if 'server_log' in path.name or 'server_chat_log' in path.name:
            continue
        if path.is_symlink():
            raise RuntimeError(f'Unexpected symlink in cluster: {rel}')
        if path.is_file():
            before = path.stat()
            with path.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise RuntimeError(f'File changed while reading: {rel}')
            result[str(rel)] = {'size': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest}
    return result


def snapshot(cluster, output, attempts=4, quiet_seconds=3):
    if not (cluster / 'cluster.ini').is_file():
        raise RuntimeError('Missing cluster.ini')
    for shard in ('Master', 'Caves'):
        if not any((cluster / shard / 'save/session').rglob('*')):
            raise RuntimeError(f'Missing {shard} save data')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    for attempt in range(attempts):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        final = output / f'dst-{stamp}.tar.gz'
        temporary = output / (final.name + '.partial')
        try:
            before = inventory(cluster)
            time.sleep(quiet_seconds)
            if inventory(cluster) != before:
                raise RuntimeError('Save files changed; waiting for a quiet interval')
            with temporary.open('xb') as raw:
                temporary.chmod(0o600)
                with tarfile.open(fileobj=raw, mode='w:gz') as archive:
                    for relative in before:
                        archive.add(cluster / relative, arcname=f'Cluster_1/{relative}', recursive=False)
                    manifest = json.dumps({'created_utc': stamp, 'files': before,
                        'note': 'Stable on-disk snapshot; excludes unsaved memory, logs and cluster_token.txt.'}, indent=2).encode()
                    member = tarfile.TarInfo('backup-manifest.json')
                    member.size = len(manifest)
                    member.mode = 0o600
                    archive.addfile(member, io.BytesIO(manifest))
            if inventory(cluster) != before:
                raise RuntimeError('Save files changed during backup')
            with tarfile.open(temporary, 'r:gz') as archive:
                for relative, expected in before.items():
                    with archive.extractfile(f'Cluster_1/{relative}') as f:
                        if hashlib.file_digest(f, 'sha256').hexdigest() != expected['sha256']:
                            raise RuntimeError(f'Archive verification failed: {relative}')
            temporary.rename(final)
            return final
        except (OSError, RuntimeError, tarfile.TarError) as exc:
            temporary.unlink(missing_ok=True)
            if attempt == attempts - 1:
                raise RuntimeError(f'Could not create a stable backup: {exc}') from exc
            time.sleep(quiet_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', type=Path, default=ROOT / 'data/DoNotStarveTogether/Cluster_1')
    parser.add_argument('--output', type=Path, default=ROOT / 'backups/daily')
    args = parser.parse_args()
    print(snapshot(args.cluster, args.output))
