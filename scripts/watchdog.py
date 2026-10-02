#!/usr/bin/env python3
"""Update an empty running DST server only when Steam publishes a newer build."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from snapshot import snapshot

ROOT = Path(__file__).resolve().parent.parent
CLUSTER = ROOT / 'data/DoNotStarveTogether/Cluster_1'
STATE = ROOT / 'runtime/watchdog'
SHARDS = {'master': 'Master', 'cave': 'Caves'}
RPC = '''import json,sys,xmlrpc.client
from supervisor.xmlrpc import SupervisorTransport
s=xmlrpc.client.ServerProxy('http://localhost',transport=SupervisorTransport(None,None,'unix:///var/run/supervisor.sock'))
if sys.argv[1]=='status': print(json.dumps(s.supervisor.getAllProcessInfo()))
elif sys.argv[1]=='shutdown':
    for shard in ('master','cave'): s.supervisor.sendProcessStdin('dst-server:dst-server-'+shard,'c_shutdown(true)\\n')
    s.supervisor.shutdown()
else: s.supervisor.sendProcessStdin('dst-server:dst-server-'+sys.argv[1],sys.argv[2]+'\\n')
'''


def log(message):
    print(datetime.now(timezone.utc).isoformat(timespec='seconds'), message, flush=True)


def docker(*args, timeout=30):
    result = subprocess.run(['bash', str(ROOT/'scripts/docker.sh'), *args], cwd=ROOT,
                            text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Raw game/Steam output can contain account information. Keep errors generic.
        raise RuntimeError('Docker operation failed: ' + args[0])
    return result.stdout


def rpc(container, action, code=''):
    return docker('exec', container, 'python3', '-c', RPC, action, code)


def container_state(container):
    return json.loads(docker('inspect', container))[0]


def processes(container):
    result = json.loads(rpc(container, 'status'))
    names = {'dst-server-master', 'dst-server-cave'}
    if {p['name'] for p in result} != names or any(p['statename'] != 'RUNNING' for p in result):
        raise RuntimeError('Both shards must be RUNNING; refusing an automatic restart.')
    return result


def public_build(output):
    # Parse the Valve KeyValues tree, not the first buildid (which may be a beta).
    tokens = re.findall(r'"([^"\n]*)"|([{}])', output)
    tokens = [a or b for a, b in tokens]
    start = tokens.index('343050') + 1
    def obj(i):
        if tokens[i] != '{': raise ValueError('Expected object')
        result = {}; i += 1
        while tokens[i] != '}':
            key = tokens[i]; i += 1
            if tokens[i] == '{': value, i = obj(i)
            else: value = tokens[i]; i += 1
            result[key] = value
        return result, i + 1
    data, _ = obj(start)
    value = int(data['depots']['branches']['public']['buildid'])
    if value <= 0: raise ValueError('Invalid Steam build')
    return value


def installed_build():
    text = (ROOT/'runtime/game/steamapps/appmanifest_343050.acf').read_text()
    match = re.search(r'"buildid"\s+"(\d+)"', text)
    if not match: raise RuntimeError('Missing installed Steam build')
    return int(match[1])


def log_path(shard):
    return CLUSTER / SHARDS[shard] / 'server_log.txt'


def offset(shard):
    return log_path(shard).stat().st_size


def log_since(shard, pos):
    with log_path(shard).open('rb') as f:
        f.seek(pos)
        return f.read().decode(errors='replace')


def response(text, marker):
    # Do not mistake RemoteCommandInput's echo for executed Lua output.
    return re.search(r'^\[[\d:]+\]: ' + re.escape(marker) + r'(?:\t([^\r\n]*))?\s*$', text, re.M)


def command(container, shard, code, seconds=45):
    marker = 'DST_WATCHDOG_' + uuid.uuid4().hex
    pos = offset(shard)
    rpc(container, shard, code.replace('MARKER', json.dumps(marker)))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        match = response(log_since(shard, pos), marker)
        if match: return (match[1] or '').strip()
        time.sleep(1)
    raise RuntimeError(f'{shard}: no confirmed response (no restart attempted).')


def empty(container):
    for shard in SHARDS:
        count = command(container, shard,
            'assert(TheWorld and TheNet:GetIsServer()); '
            'print(MARKER, math.max(#AllPlayers, #GetPlayerClientTable()))')
        if not count.isdigit(): raise RuntimeError('Unknown player count; refusing update.')
        if int(count): return False
    return True


def gate(container, shard, close):
    if close:
        code = ('TheNet:SetAllowNewPlayersToConnect(false); '
                'if DSTWatchdogLease then DSTWatchdogLease:Cancel() end; '
                'DSTWatchdogLease=TheWorld:DoStaticTaskInTime(300,function() '
                'TheNet:SetAllowNewPlayersToConnect(true); DSTWatchdogLease=nil end); print(MARKER)')
    else:
        code = ('TheNet:SetAllowNewPlayersToConnect(true); '
                'if DSTWatchdogLease then DSTWatchdogLease:Cancel(); DSTWatchdogLease=nil end; print(MARKER)')
    command(container, shard, code)


def cleanup_complete(text):
    return all(s in text for s in ('Serializing world:', 'lua_close took', 'Shutting down'))


def wait_online(container, previous_start, target, seconds=1200):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        info = container_state(container)
        if info['State']['Running'] and info['State']['StartedAt'] != previous_start:
            try:
                processes(container)
                # Logs are truncated on each game start. Require current registration/link.
                texts = {s: log_path(s).read_text(errors='replace') for s in SHARDS}
                if ('Server registered' in texts['master'] and
                        all('is now connected' in text for text in texts.values())):
                    for shard in SHARDS:
                        command(container, shard, 'assert(TheWorld and TheNet:GetIsServer()); print(MARKER)')
                    if installed_build() < target: raise RuntimeError('Update did not install the expected build.')
                    return
            except RuntimeError:
                pass
        time.sleep(5)
    raise RuntimeError('Update readiness timed out; inspect logs before another restart.')


def update(container, target, info):
    closed = []; shutting_down = False
    try:
        for shard in SHARDS:
            closed.append(shard)
            gate(container, shard, True)
        # Let any connection already in flight appear in the client tables.
        time.sleep(5)
        if not empty(container):
            log('A player connected; deferring update.'); return
        for shard in SHARDS:
            command(container, shard,
                'ShardGameIndex:SaveCurrent(function() print(MARKER) end)', seconds=60)
        archive = snapshot(CLUSTER, ROOT/'backups/pre-update')
        log('Verified backup: ' + str(archive.relative_to(ROOT)))
        for shard in SHARDS:
            gate(container, shard, True)
        if not empty(container):
            log('A player connected during preparation; deferring update.'); return
        procs = processes(container)
        positions = {s: offset(s) for s in SHARDS}
        # Persist a latch BEFORE shutdown. A failed/interrupted update cannot loop.
        (STATE/'needs-review').write_text(f'Update to Steam build {target} started; clear only after checking readiness.\n')
        shutting_down = True
        rpc(container, 'shutdown')
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            current = container_state(container)
            if not current['State']['Running'] or current['State']['StartedAt'] != info['State']['StartedAt']:
                break
            time.sleep(3)
        else:
            # Known native cleanup hang: never force a live or unconfirmed save.
            if not all(cleanup_complete(log_since(s, positions[s])) for s in SHARDS):
                raise RuntimeError('Shutdown not confirmed; leaving recovery to the operator.')
            current = container_state(container)
            if current['State']['StartedAt'] == info['State']['StartedAt']:
                log('Both shards saved and closed Lua; terminating hung native cleanup processes.')
                docker('exec', container, 'kill', '-KILL', *(str(p['pid']) for p in procs))
        wait_online(container, info['State']['StartedAt'], target)
        (STATE/'needs-review').unlink()
        (STATE/'last-update.json').write_text(json.dumps({'build': installed_build(),
            'completed_utc': datetime.now(timezone.utc).isoformat()}))
        log('Updated successfully; both worlds online and linked.')
    finally:
        if not shutting_down:
            for shard in closed:
                try: gate(container, shard, False)
                except Exception: log(f'{shard}: reopen failed; the five-minute game lease will retry.')


def run(check_only=False):
    if (STATE/'needs-review').exists():
        raise RuntimeError('Previous update needs review; see runtime/watchdog/needs-review.')
    container = docker('compose', 'ps', '--all', '-q', 'server').strip()
    if not container or not container_state(container)['State']['Running']:
        log('Server is stopped; leaving it stopped.'); return
    info = container_state(container)
    processes(container)
    if info['HostConfig']['RestartPolicy']['Name'] not in ('always', 'unless-stopped'):
        raise RuntimeError('Container must have automatic crash restart enabled.')
    current = installed_build()
    output = docker('exec', container, 'timeout', '180', '/opt/steamcmd/steamcmd.sh',
        '+login', 'anonymous', '+app_info_update', '1', '+app_info_print', '343050', '+quit', timeout=210)
    latest = public_build(output)
    log(f'Steam build: installed={current}, public={latest}.')
    if latest <= current:
        log('Already current; no restart.'); return
    if check_only:
        log('Update available; check-only mode makes no changes.'); return
    if not empty(container):
        log('Players online; update deferred until a later check.'); return
    if container_state(container)['State']['StartedAt'] != info['State']['StartedAt']:
        raise RuntimeError('Container changed during inspection; defer until the next check.')
    update(container, latest, info)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-only', action='store_true', help='Check Steam without saves or restarts')
    args = p.parse_args()
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE/'lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: log('Another watchdog is active.'); return
        try: run(args.check_only)
        except Exception as exc:
            log('FAILED: ' + str(exc)); sys.exit(1)


if __name__ == '__main__': main()
