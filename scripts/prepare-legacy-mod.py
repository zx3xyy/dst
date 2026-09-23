#!/usr/bin/env python3
"""Preserve Moving Box using its official Steam legacy archive."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
CLUSTER=ROOT/'data/DoNotStarveTogether/Cluster_1'
MOD='1079538195'


def prepare(cluster=CLUSTER, runtime=ROOT/'runtime'):
    enabled=any(re.search(r'\["workshop-'+MOD+r'"\]\s*=\s*\{', p.read_text()) for p in cluster.glob('*/modoverrides.lua'))
    if not enabled:
        return
    target=cluster/'mods'/('workshop-'+MOD)
    if not (target/'modinfo.lua').is_file():
        if target.exists(): raise RuntimeError('Incomplete local Moving Box directory; inspect before replacing.')
        runtime.mkdir(parents=True,exist_ok=True)
        data=urllib.parse.urlencode({'itemcount':1,'publishedfileids[0]':MOD}).encode()
        request=urllib.request.Request('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',data=data)
        metadata=json.load(urllib.request.urlopen(request,timeout=30))
        detail=metadata['response']['publishedfiledetails'][0]
        if detail['result']!=1 or detail.get('banned'): raise RuntimeError('Steam did not provide an available mod.')
        url=detail['file_url']; host=urllib.parse.urlparse(url).hostname or ''
        if not url.startswith('https://') or not (host.endswith('.steamusercontent.com') or host=='steamusercontent.com'):
            raise RuntimeError('Unexpected Steam download host.')
        with urllib.request.urlopen(url,timeout=60) as response:
            payload=response.read(20*1024**2+1)
        if len(payload)>20*1024**2: raise RuntimeError('Unexpectedly large legacy archive.')
        archive=runtime/'moving-box.zip'; archive.write_bytes(payload)
        (runtime/'moving-box-details.json').write_text(json.dumps(metadata,indent=2))
        target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='.moving-box-') as temp:
            staged=Path(temp)/'mod'; staged.mkdir()
            with zipfile.ZipFile(archive) as z:
                if sum(i.file_size for i in z.infolist())>100*1024**2: raise RuntimeError('Archive expands too far.')
                for entry in z.infolist():
                    rel=PurePosixPath(entry.filename.replace('\\','/'))
                    if rel.is_absolute() or '..' in rel.parts or stat.S_ISLNK(entry.external_attr>>16):
                        raise RuntimeError('Unsafe mod archive path.')
                    p=staged/rel
                    if entry.is_dir(): p.mkdir(parents=True,exist_ok=True)
                    else:
                        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(entry))
            if not (staged/'modinfo.lua').is_file() or not (staged/'modmain.lua').is_file():
                raise RuntimeError('Incomplete legacy mod.')
            staged.rename(target)
        print('Installed official Moving Box archive; SHA256:',hashlib.sha256(payload).hexdigest())
    else:
        print('Existing Moving Box preserved.')
    config=target.parent/'dedicated_server_mods_setup.lua'
    if config.exists():
        original=config.read_text()
        updated=re.sub(r'^\s*ServerModSetup\("'+MOD+r'"\)\s*$', '-- Moving Box is installed locally from its official Steam legacy archive.', original, flags=re.M)
        if updated!=original: config.write_text(updated)


if __name__=='__main__': prepare()
