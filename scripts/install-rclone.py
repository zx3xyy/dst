#!/usr/bin/env python3
"""Install a pinned, SHA256-verified rclone under the project runtime directory."""
import hashlib
from pathlib import Path
import platform
import urllib.request
import zipfile

root=Path(__file__).resolve().parent.parent/'runtime/tools'
version='v1.75.1'
if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):
    raise SystemExit('This deployment supports Linux x86_64.')
root.mkdir(parents=True,exist_ok=True)
name=f'rclone-{version}-linux-amd64.zip'; url=f'https://downloads.rclone.org/{version}/'
checks=urllib.request.urlopen(url+'SHA256SUMS',timeout=30).read().decode()
expected=next(s.split()[0] for s in checks.splitlines() if s.split() and s.split()[-1].lstrip('*')==name)
p=root/name
if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
    urllib.request.urlretrieve(url+name,p)
if hashlib.sha256(p.read_bytes()).hexdigest()!=expected: raise SystemExit('rclone checksum mismatch.')
with zipfile.ZipFile(p) as z:
    temporary=root/'rclone.partial'
    temporary.write_bytes(z.read(f'rclone-{version}-linux-amd64/rclone'))
    temporary.chmod(0o755);temporary.replace(root/'rclone')
print('Verified rclone installed:',version)
