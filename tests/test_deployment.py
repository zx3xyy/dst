import importlib.util
import json
import os
from pathlib import Path
import tarfile
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parent.parent

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/filename)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

importer=load('importer','import-save.py')
control=load('control','serverctl.py')

class DeploymentTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'runtime/tests').mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'runtime/tests');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.token=self.root/'token';self.token.write_text('example-test-token')
        self.target=self.root/'deploy/Cluster_1'
        self.files={'Cluster_9/cluster.ini':b'[GAMEPLAY]\ngame_mode=survival\n',
            'Cluster_9/Master/save/session/test/0000000001':b'world and player data',
            'Cluster_9/Caves/save/session/test/0000000001':b'cave data',
            'Cluster_9/Master/modoverrides.lua':b'return {["workshop-1079538195"]={enabled=true}}',
            'Cluster_9/adminlist.txt':b'KU_example\n'}
    def archive(self,extra=None):
        path=self.root/'world.zip'
        with zipfile.ZipFile(path,'w') as z:
            for n,b in {**self.files,**(extra or {})}.items():z.writestr(n,b)
        return path
    def test_zip_preserves_save_admins_and_refuses_overwrite(self):
        archive=self.archive();importer.import_save(archive,self.target,self.token)
        self.assertEqual((self.target/'Master/save/session/test/0000000001').read_bytes(),b'world and player data')
        self.assertEqual((self.target/'adminlist.txt').read_text(),'KU_example\n')
        self.assertEqual((self.target/'cluster_token.txt').stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):importer.import_save(archive,self.target,self.token)
    def test_tar_backup_import(self):
        source=self.root/'source';source.mkdir()
        for n,b in self.files.items():
            p=source/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        archive=self.root/'world.tar.gz'
        with tarfile.open(archive,'w:gz') as t:t.add(source/'Cluster_9',arcname='Cluster_1')
        importer.import_save(archive,self.target,self.token)
        self.assertEqual((self.target/'Caves/save/session/test/0000000001').read_bytes(),b'cave data')
    def test_bad_paths_and_missing_token_leave_no_deployment(self):
        with self.assertRaises(ValueError):importer.import_save(self.archive({'Cluster_9/../../escape':b'bad'}),self.target,self.token)
        self.assertFalse(self.target.exists());self.assertFalse((self.root/'escape').exists())
        with self.assertRaises(ValueError):importer.import_save(self.archive(),self.target)
        self.assertFalse(self.target.exists())
    def test_backup_manifest_mismatch_does_not_publish_cluster(self):
        manifest=json.dumps({'files':{'Master/save/session/test/0000000001':{'sha256':'0'*64}}}).encode()
        with self.assertRaises(ValueError):
            importer.import_save(self.archive({'backup-manifest.json':manifest}),self.target,self.token)
        self.assertFalse(self.target.exists())
    def test_admin_add_is_idempotent_and_rejects_names(self):
        p=self.root/'adminlist.txt'
        control.add_admins(p,['KU_a','KU_b']);control.add_admins(p,['KU_a'])
        self.assertEqual(p.read_text(),'KU_a\nKU_b\n')
        with self.assertRaises(ValueError):control.add_admins(p,['some player'])
    def test_rollback_backs_up_before_exactly_one_request(self):
        events=[]
        with patch('sys.argv',['serverctl.py','rollback','2']), patch.object(control.subprocess,'run',side_effect=lambda *a,**k: events.append('backup')), patch.object(control,'send',side_effect=lambda shard,cmd:events.append((shard,cmd))):
            control.main()
        self.assertEqual(events,['backup',('master','c_rollback(2)')])
    def test_rollback_not_sent_when_backup_fails(self):
        with patch('sys.argv',['serverctl.py','rollback','2']), patch.object(control.subprocess,'run',side_effect=RuntimeError('disk full')), patch.object(control,'send') as send:
            with self.assertRaises(RuntimeError):control.main()
            send.assert_not_called()
    def test_group_wrapper_preserves_multiline_arguments(self):
        bindir=self.root/'bin';bindir.mkdir()
        programs={
            'docker': 'import json,sys\nif sys.argv[1]=="info": sys.exit(1)\nprint(json.dumps(sys.argv[1:]))\n',
            'id': 'print("docker")\n',
            'sg': 'import os,sys\nos.execv("/bin/sh",["sh","-c",sys.argv[3]])\n',
        }
        for name,body in programs.items():
            f=bindir/name;f.write_text('#!'+sys.executable+'\n'+body);f.chmod(0o755)
        args=['exec','-T','server','python3','-c','print("quoted")\nprint("$HOME; `literal`")']
        r=subprocess.run(['bash',str(ROOT/'scripts/docker.sh'),*args],env={**os.environ,'PATH':str(bindir)+':'+os.environ['PATH']},capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(r.stdout),args)

if __name__=='__main__':unittest.main()
