import contextlib
import io
import json
from pathlib import Path
import sqlite3
import socket
import tempfile
import unittest
from unittest.mock import patch
from scripts import storage_paths as s

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';self.root.mkdir();self.source=self.root/'data';self.source.mkdir()
        self.target=Path(self.temp.name)/'disk'/'news-data'
        self.db=sqlite3.connect(self.source/'news-atlas.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('CREATE TABLE records (value TEXT)');self.db.execute("INSERT INTO records VALUES ('keep me')");self.db.commit();self.addCleanup(self.db.close)
        (self.source/'private').mkdir(mode=0o700);(self.source/'private'/'key.massive-key').write_text('isolated-test-key');(self.source/'private'/'key.massive-key').chmod(0o600)

    def test_verified_relocation_includes_wal_and_private_files(self):
        with contextlib.redirect_stdout(io.StringIO()):s.relocate(self.root,self.source,self.target)
        self.assertTrue(self.source.is_symlink());self.assertEqual(self.source.resolve(),self.target)
        with sqlite3.connect(self.target/'news-atlas.sqlite3') as db:self.assertEqual(db.execute('select value from records').fetchone()[0],'keep me')
        self.assertEqual((self.target/'private'/'key.massive-key').stat().st_mode&0o777,0o600)
        self.assertEqual(s.load(self.root),self.target)
        self.assertEqual(len(list(self.root.glob('.data-backup-*'))),1)

    def test_relocation_skips_chat_socket_and_pid(self):
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        sock.bind(str(self.source/'private'/'chat.sock'))
        (self.source/'private'/'chat-process.json').write_text('{"pid":123}')
        self.target.parent.mkdir(parents=True)
        s.copy_verified(self.source,self.target)
        self.assertFalse((self.target/'private'/'chat.sock').exists())
        self.assertFalse((self.target/'private'/'chat-process.json').exists())
        self.assertTrue((self.target/'private'/'key.massive-key').exists())

    def test_no_overwrite_or_recursive_target(self):
        self.target.mkdir(parents=True);(self.target/'existing').write_text('untouched')
        with self.assertRaisesRegex(RuntimeError,'not empty'):s.relocate(self.root,self.source,self.target)
        with self.assertRaisesRegex(RuntimeError,'contain each other'):s.relocate(self.root,self.source,self.source/'nested')
        self.assertFalse(self.source.is_symlink());self.assertEqual((self.target/'existing').read_text(),'untouched')

    def test_state_failure_restores_original_directory(self):
        with patch.object(s,'save',side_effect=OSError('disk full')),self.assertRaises(OSError):s.relocate(self.root,self.source,self.target)
        self.assertTrue(self.source.is_dir());self.assertFalse(self.source.is_symlink());self.assertTrue((self.source/'news-atlas.sqlite3').exists())

    def test_missing_saved_mount_does_not_fallback(self):
        (self.root/s.STATE).write_text(json.dumps({'data_dir':str(self.target),'mountpoint':'/missing-test-disk'}))
        with self.assertRaisesRegex(RuntimeError,'refusing to fall back'):s.load(self.root)

    def test_no_other_disk_still_offers_custom_path(self):
        options=[]
        def choose(label,labels):options.extend(labels);return len(labels)-1
        with patch.object(s,'disk_candidates',return_value=[]),patch('builtins.input',return_value=str(self.target)),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.choose_path(self.source,True,choose),self.target)
        self.assertIn('Custom directory path',options)
        with patch.object(s,'disk_candidates',return_value=[]),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(s.choose_path(self.source,False,choose),self.source)

    def test_disk_discovery_excludes_system_loop_and_unmounted(self):
        tree={'blockdevices':[{'name':'loop1','type':'loop','mountpoints':['/snap/a'],'ro':True},{'name':'nvme0','type':'disk','children':[{'type':'part','mountpoints':['/'],'fstype':'ext4'}]},{'name':'sdb','type':'disk','children':[{'type':'part','mountpoints':[None],'fstype':'ext4'}]}]}
        self.assertEqual(s.disk_candidates(self.source,tree),[])


    def test_link_activation_failure_restores_original(self):
        real=s.os.replace
        def replace(src,dst):
            if Path(dst)==self.source:raise OSError('link activation failed')
            return real(src,dst)
        with patch.object(s.os,'replace',side_effect=replace),self.assertRaises(OSError):s.relocate(self.root,self.source,self.target)
        self.assertFalse(self.source.is_symlink());self.assertTrue((self.source/'news-atlas.sqlite3').exists())

    def test_mounted_secondary_disk_is_offered_with_capacity(self):
        import stat
        from types import SimpleNamespace
        point=Path('/example-mounted-data')
        tree={'blockdevices':[{'name':'system','type':'disk','children':[{'mountpoints':['/'],'fstype':'ext4'}]},{'name':'extra','type':'disk','children':[{'mountpoints':[str(point)],'fstype':'ext4'}]}]}
        def fake_stat(path,*args,**kwargs):return SimpleNamespace(st_dev=2 if path==point else 1,st_mode=stat.S_IFDIR)
        with patch.object(Path,'stat',fake_stat),patch.object(s.os.path,'ismount',return_value=True),patch.object(s.os,'access',return_value=True),patch.object(s.shutil,'disk_usage',return_value=SimpleNamespace(free=123456789)):
            found=s.disk_candidates(self.source,tree)
        self.assertEqual(found,[{'mount':point,'disk':'extra','free':123456789}])
