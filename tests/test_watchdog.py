import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('watchdog', ROOT/'scripts/watchdog.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)

INFO = {'State': {'Running': True, 'StartedAt': 'old'},
        'HostConfig': {'RestartPolicy': {'Name': 'unless-stopped'}}}
STEAM = '"343050" { "depots" { "branches" { "beta" { "buildid" "999" } "public" { "buildid" "20" } } } }'

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        state = patch.object(w, 'STATE', Path(self.tmp.name)); state.start(); self.addCleanup(state.stop)

    def test_public_branch_not_beta(self):
        self.assertEqual(w.public_build(STEAM), 20)
        with self.assertRaises((ValueError, KeyError, IndexError)):
            w.public_build('Steam connection failed')

    def test_command_echo_is_not_a_response(self):
        self.assertIsNone(w.response('[00:00:01]: RemoteCommandInput: "print(\"nonce\")"', 'nonce'))
        self.assertIsNotNone(w.response('[00:00:01]: nonce\t0\t\n', 'nonce'))

    def test_stopped_server_stays_stopped(self):
        with patch.object(w, 'docker', return_value=''), patch.object(w, 'update') as update:
            w.run(); update.assert_not_called()

    def run_check(self, current, occupied=False, check_only=False):
        with patch.object(w, 'docker', side_effect=['container', STEAM]), \
             patch.object(w, 'container_state', return_value=INFO), \
             patch.object(w, 'processes'), patch.object(w, 'installed_build', return_value=current), \
             patch.object(w, 'empty', return_value=not occupied), patch.object(w, 'update') as update:
            w.run(check_only)
            return update.call_count

    def test_no_restart_when_current_or_occupied_or_check_only(self):
        self.assertEqual(self.run_check(20), 0)
        self.assertEqual(self.run_check(10, occupied=True), 0)
        self.assertEqual(self.run_check(10, check_only=True), 0)
        self.assertEqual(self.run_check(10), 1)

    def test_failed_update_latch_blocks_retries(self):
        (w.STATE/'needs-review').write_text('failed')
        with patch.object(w, 'docker') as docker:
            with self.assertRaises(RuntimeError): w.run()
            docker.assert_not_called()

    def test_cave_player_prevents_update(self):
        with patch.object(w, 'command', side_effect=['0', '1']):
            self.assertFalse(w.empty('c'))
        with patch.object(w, 'command', return_value='unknown'):
            with self.assertRaises(RuntimeError): w.empty('c')

    def test_failed_backup_reopens_connections_without_shutdown(self):
        with patch.object(w, 'gate') as gate, patch.object(w, 'empty', return_value=True), \
             patch.object(w.time, 'sleep'), patch.object(w, 'command'), \
             patch.object(w, 'snapshot', side_effect=RuntimeError('disk full')), patch.object(w, 'rpc') as rpc:
            with self.assertRaises(RuntimeError): w.update('c', 20, INFO)
            rpc.assert_not_called()
            self.assertEqual(gate.call_args_list[-2].args, ('c', 'master', False))
            self.assertEqual(gate.call_args_list[-1].args, ('c', 'cave', False))
            self.assertFalse((w.STATE/'needs-review').exists())

    def test_player_arriving_after_gate_aborts_and_reopens(self):
        with patch.object(w, 'gate') as gate, patch.object(w, 'empty', return_value=False), \
             patch.object(w.time, 'sleep'), patch.object(w, 'snapshot') as backup, patch.object(w, 'rpc') as rpc:
            w.update('c', 20, INFO)
            backup.assert_not_called(); rpc.assert_not_called()
            self.assertEqual(gate.call_count, 4)

    def test_update_order_and_failure_latch(self):
        for ready in (True, False):
            with self.subTest(ready=ready):
                events = []
                with patch.object(w, 'gate'), patch.object(w, 'empty', return_value=True), \
                     patch.object(w.time, 'sleep'), patch.object(w, 'command', side_effect=lambda *a, **k: events.append('save')), \
                     patch.object(w, 'snapshot', side_effect=lambda *a: events.append('backup') or ROOT/'backups/test.tar.gz'), \
                     patch.object(w, 'processes', return_value=[]), patch.object(w, 'offset', return_value=0), \
                     patch.object(w, 'rpc', side_effect=lambda *a: events.append('shutdown')), \
                     patch.object(w, 'container_state', return_value={'State': {'Running': False}}), \
                     patch.object(w, 'installed_build', return_value=20), \
                     patch.object(w, 'wait_online', side_effect=None if ready else RuntimeError('not ready')):
                    if ready: w.update('c', 20, INFO)
                    else:
                        with self.assertRaises(RuntimeError): w.update('c', 20, INFO)
                self.assertEqual(events, ['save', 'save', 'backup', 'shutdown'])
                self.assertEqual((w.STATE/'needs-review').exists(), not ready)

    def test_unconfirmed_shutdown_never_forces_kill(self):
        with patch.object(w, 'gate'), patch.object(w, 'empty', return_value=True), \
             patch.object(w.time, 'sleep'), patch.object(w, 'command'), \
             patch.object(w, 'snapshot', return_value=ROOT/'backups/test.tar.gz'), \
             patch.object(w, 'processes', return_value=[{'pid': 123}]), \
             patch.object(w, 'offset', return_value=0), patch.object(w, 'rpc'), \
             patch.object(w.time, 'monotonic', side_effect=[0, 100]), \
             patch.object(w, 'log_since', return_value='Serializing world:'), patch.object(w, 'docker') as docker:
            with self.assertRaises(RuntimeError): w.update('c', 20, INFO)
            docker.assert_not_called()
            self.assertTrue((w.STATE/'needs-review').exists())

    def test_force_cleanup_requires_all_shutdown_evidence(self):
        for text in ['Serializing world:', 'lua_close took 1 seconds\nShutting down', '']:
            self.assertFalse(w.cleanup_complete(text))
        self.assertTrue(w.cleanup_complete('Serializing world:\nlua_close took 1 seconds\nShutting down'))

if __name__ == '__main__': unittest.main()
