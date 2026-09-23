#!/usr/bin/env python3
"""Import a local cluster ZIP without overwriting an existing deployment."""
import configparser
import hashlib
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import zipfile

root = Path(__file__).resolve().parent.parent
source = Path(sys.argv[1]).resolve()
target = root / 'data/DoNotStarveTogether/Cluster_1'
if target.exists():
    sys.exit('Target exists; refusing to overwrite the deployed world.')
with zipfile.ZipFile(source) as z:
    clusters = [n[:-len('/cluster.ini')] for n in z.namelist()
                if n.endswith('/cluster.ini') and not n.startswith('__MACOSX/')]
    if len(clusters) != 1:
        sys.exit('Expected exactly one cluster in ZIP.')
    prefix = clusters[0] + '/'
    files = []
    for entry in z.infolist():
        if not entry.filename.startswith(prefix) or entry.is_dir():
            continue
        relative = PurePosixPath(entry.filename[len(prefix):])
        if relative.is_absolute() or '..' in relative.parts:
            sys.exit('Unsafe archive path.')
        if stat.S_ISLNK(entry.external_attr >> 16):
            sys.exit('Archive symlinks are not supported.')
        if any(p == '.DS_Store' or p.startswith('._') for p in relative.parts):
            continue
        files.append((entry, relative))
    if sum(e.file_size for e, _ in files) > 2 * 1024**3:
        sys.exit('Archive unexpectedly large; inspect manually.')
    if z.testzip():
        sys.exit('Archive integrity check failed.')
    for entry, relative in files:
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(z.read(entry))

def edit_ini(path, changes):
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(path, encoding='utf-8-sig')
    for section, values in changes.items():
        if not ini.has_section(section):
            ini.add_section(section)
        for key, value in values.items():
            ini.set(section, key, str(value))
    with path.open('w') as f:
        ini.write(f)

edit_ini(target / 'cluster.ini', {'GAMEPLAY': {'pause_when_empty': 'true'}})
mods = set()
for shard, port, steam, auth in [('Master',10999,12346,8766), ('Caves',11000,12347,8767)]:
    edit_ini(target / shard / 'server.ini', {
        'NETWORK': {'server_port': port},
        'STEAM': {'master_server_port': steam, 'authentication_port': auth},
    })
    modfile = target / shard / 'modoverrides.lua'
    if modfile.exists():
        # Match top-level workshop keys, not IDs embedded in mod options.
        mods.update(re.findall(r'^  \["workshop-(\d+)"\]\s*=\s*\{', modfile.read_text(), re.M))
moddir = target / 'mods'
moddir.mkdir(exist_ok=True)
(moddir / 'dedicated_server_mods_setup.lua').write_text(
    ''.join(f'ServerModSetup("{m}")\n' for m in sorted(mods)))
shutil.copyfile(root / 'incoming/cluster_token.txt', target / 'cluster_token.txt')
(target / 'cluster_token.txt').chmod(0o600)
print(f'Imported {len(files)} files; configured {len(mods)} mods.')
print(f'Original ZIP SHA256: {hashlib.sha256(source.read_bytes()).hexdigest()}')
