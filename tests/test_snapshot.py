import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('snapshot', ROOT / 'scripts/snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'runtime/tests').mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'runtime/tests')
        self.addCleanup(self.temp.cleanup)
        self.cluster = Path(self.temp.name) / 'Cluster_1'
        self.output = Path(self.temp.name) / 'backups'
        for shard in ('Master', 'Caves'):
            p = self.cluster / shard / 'save/session/example'
            p.mkdir(parents=True)
            (p / '0000000001').write_bytes(b'original world data')
        (self.cluster / 'cluster.ini').write_text('[GAMEPLAY]\n')
        (self.cluster / 'cluster_token.txt').write_text('private token')
        (self.cluster / 'Master/server_log.txt').write_text('private log')

    def test_restore_payload_and_exclude_token_and_logs(self):
        result = snapshot.snapshot(self.cluster, self.output, quiet_seconds=0)
        with tarfile.open(result) as archive:
            names = archive.getnames()
            self.assertNotIn('Cluster_1/cluster_token.txt', names)
            self.assertNotIn('Cluster_1/Master/server_log.txt', names)
            self.assertEqual(archive.extractfile('Cluster_1/Master/save/session/example/0000000001').read(),
                             b'original world data')
            self.assertIn('backup-manifest.json', names)
        self.assertEqual(result.stat().st_mode & 0o777, 0o600)

    def test_changes_during_archive_never_publish_backup(self):
        real_add = tarfile.TarFile.add
        def changing_add(archive, name, **kwargs):
            real_add(archive, name, **kwargs)
            if Path(name).name == '0000000001':
                Path(name).write_bytes(b'new world data')
        with patch.object(tarfile.TarFile, 'add', changing_add):
            with self.assertRaises(RuntimeError):
                snapshot.snapshot(self.cluster, self.output, attempts=1, quiet_seconds=0)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
