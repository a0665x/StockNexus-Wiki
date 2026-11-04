import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from scripts import docker_launch as d

class DockerLaunchTests(unittest.TestCase):
    def setUp(self):
        self.real_host_checks=d.host_checks
        host=patch.object(d,'host_checks');host.start();self.addCleanup(host.stop)
        patcher=patch.object(d.storage_paths,'choose_path',side_effect=lambda current,*args,**kwargs:Path(current).resolve())
        patcher.start();self.addCleanup(patcher.stop)

    def args(self,**kw):
        import argparse
        return argparse.Namespace(non_interactive=True,tailscale='off',https_port=8443,**kw)

    def test_global_lock_prevents_concurrent_mutations(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(d.tempfile,'gettempdir',return_value=folder):
            with d.startup_lock():
                with self.assertRaisesRegex(RuntimeError,'Another'):
                    with d.startup_lock():pass
            with d.startup_lock():pass

    def test_fixed_project_ignores_environment_project_names(self):
        self.assertEqual(d.COMPOSE[-2:],['-p','news-atlas'])
        self.assertEqual(d.PORT,8765)

    def test_preflight_probes_configured_address_not_all_interfaces(self):
        with tempfile.TemporaryDirectory() as folder:
            for bind in ('127.0.0.1', '0.0.0.0'):
                config={'services':{'atlas':{'ports':[{'published':'8765','target':8765,'host_ip':bind}],
                    'volumes':[{'target':'/app/data','source':folder}]}}}
                # Tailscale owns another interface; only the loopback bind is free.
                with self.subTest(bind=bind), patch.object(d,'json_run',return_value=config), \
                     patch.object(d,'containers',return_value=[]), patch.object(d,'run',return_value=''), \
                     patch.object(d.launch,'available',side_effect=lambda port,host: host=='127.0.0.1') as probe, \
                     contextlib.redirect_stdout(io.StringIO()):
                    if bind=='127.0.0.1':
                        self.assertEqual(d.preflight()[2],bind)
                    else:
                        with self.assertRaisesRegex(RuntimeError,'occupied'):d.preflight()
                    probe.assert_called_once_with(8765,bind)

    def test_repeated_healthy_up_does_not_down_or_create_replica(self):
        healthy={'id':'one','labels':{'com.docker.compose.service':'atlas'},'state':{'Running':True,'Health':{'Status':'healthy'}}}
        response=MagicMock();response.__enter__.return_value.status=200
        with patch.object(d,'startup_lock',return_value=contextlib.nullcontext()),patch.object(d,'preflight',return_value=([healthy],Path('/tmp/data'),'127.0.0.1')),patch.object(d,'configure_tailscale',return_value=None),patch.object(d,'containers',return_value=[healthy]),patch.object(d,'run') as run,patch.object(d.urllib.request,'build_opener') as opener,contextlib.redirect_stdout(io.StringIO()) as output:
            opener.return_value.open.return_value=response
            self.assertEqual(d.up(self.args()),0);self.assertEqual(d.up(self.args()),0)
            commands=[c.args[0] for c in run.call_args_list]
            self.assertFalse(any('down' in c for c in commands))
            ups=[c for c in commands if 'up' in c]
            self.assertEqual(len(ups),2)
            self.assertTrue(all(c[-2:]==['--scale','atlas=1'] for c in ups))
            self.assertIn('URL: http://127.0.0.1:8765',output.getvalue())

    def test_dirty_state_cleanup_before_start_and_failure_cleanup(self):
        with patch.object(d,'startup_lock',return_value=contextlib.nullcontext()),patch.object(d,'preflight',return_value=([{'state':{},'labels':{}}],Path('/tmp/data'),'127.0.0.1')),patch.object(d,'configure_tailscale',return_value=None),patch.object(d.launch,'available',return_value=True),patch.object(d,'run') as run,patch.object(d,'containers',return_value=[]),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'Container count'):d.up(self.args())
            actions=[next(x for x in c.args[0][len(d.COMPOSE):] if x in ['build','down','up']) for c in run.call_args_list]
            self.assertEqual(actions,['build','down','up','down'])

    def test_no_tailscale_no_prompt_and_running_prompts(self):
        args=self.args();args.tailscale='auto'
        with patch.object(d.shutil,'which',return_value=None),patch.object(d.launch,'choose') as choose,contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(d.configure_tailscale(args,True));choose.assert_not_called()
        with patch.object(d.shutil,'which',return_value='/bin/tailscale'),patch.object(d.launch,'tailnet_name',return_value='test.ts.net'),patch.object(d.launch,'tailscale_json',return_value={}),patch.object(d.launch,'choose',return_value=1) as choose,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(d.configure_tailscale(args,True),('test.ts.net',8443));choose.assert_called_once()

    def test_tailscale_conflict_never_overwrites(self):
        args=self.args();args.tailscale='on'
        with patch.object(d.shutil,'which',return_value='/bin/tailscale'),patch.object(d.launch,'tailnet_name',return_value='test.ts.net'),patch.object(d.launch,'tailscale_json',return_value={'TCP':{'8443':{}}}),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'already in use'):d.configure_tailscale(args,False)

    def test_serve_same_route_reused_and_only_owned_route_stopped(self):
        state={'Web':{'test.ts.net:8443':{'Handlers':{'/':{'Proxy':d.LOCAL}}}}}
        with tempfile.TemporaryDirectory() as folder,patch.object(d.launch,'tailscale_json',return_value=state),patch.object(d.shutil,'which',return_value='/bin/tailscale'),patch.object(d,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            data=Path(folder)
            self.assertEqual(d.enable_tailscale(('test.ts.net',8443),data),'https://test.ts.net:8443');run.assert_not_called()
            d.stop_owned_tailscale(data);run.assert_not_called()
            marker=d.marker_path(data);marker.parent.mkdir();marker.write_text('{"name":"test.ts.net","port":8443,"target":"http://127.0.0.1:8765"}')
            d.stop_owned_tailscale(data);run.assert_called_once_with(['tailscale','serve','--https=8443','off']);self.assertFalse(marker.exists())

    def test_foreign_port_owner_fails_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            config={'services':{'atlas':{'ports':[{'published':'8765','target':8765}],'volumes':[{'target':'/app/data','source':folder}]}}}
            def fake_run(args,capture=False):return 'other-container' if 'publish=8765' in ' '.join(args) else ''
            with patch.object(d,'json_run',return_value=config),patch.object(d,'containers',return_value=[]),patch.object(d,'run',side_effect=fake_run) as run:
                with self.assertRaisesRegex(RuntimeError,'another container'):d.preflight()
                self.assertFalse(any(any(action in c.args[0] for action in ['down','up','stop','rm']) for c in run.call_args_list))

    def test_real_terminal_tailscale_choice_confirmation_and_urls(self):
        import os,pty,select,subprocess,sys,time
        master,slave=pty.openpty()
        code='''
from scripts import docker_launch as d
from pathlib import Path
from unittest.mock import MagicMock
healthy={'id':'one','labels':{'com.docker.compose.service':'atlas'},'state':{'Running':True,'Health':{'Status':'healthy'}}}
d.preflight=lambda:([healthy],Path('/tmp'), '127.0.0.1')
d.storage_paths.choose_path=lambda current,*args,**kwargs:current
d.host_checks=lambda data:None
d.shutil.which=lambda value:'/fake/'+value
d.launch.tailnet_name=lambda:'test.ts.net'
d.launch.tailscale_json=lambda *args:{}
d.run=lambda *args,**kwargs:''
d.containers=lambda:[healthy]
d.enable_tailscale=lambda *args:'https://test.ts.net:8443'
response=MagicMock();response.__enter__.return_value.status=200
opener=MagicMock();opener.open.return_value=response
d.urllib.request.build_opener=lambda *args:opener
raise SystemExit(d.main(['up']))
'''
        child=subprocess.Popen([sys.executable,'-u','-c',code],stdin=slave,stdout=slave,stderr=slave,cwd=d.ROOT,start_new_session=True)
        output=bytearray()
        def until(needle):
            deadline=time.monotonic()+5
            while needle.encode() not in output:
                if time.monotonic()>deadline:self.fail(output.decode(errors='replace'))
                if select.select([master],[],[],.1)[0]:output.extend(os.read(master,4096))
        try:
            until('[ Local only ]');os.write(master,b'\x1b[C\r')
            until('[ Start/update ]');os.write(master,b'\r')
            until('Tailscale URL: https://test.ts.net:8443')
            self.assertEqual(child.wait(timeout=3),0)
            self.assertIn('URL: http://127.0.0.1:8765',output.decode())
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=3);os.close(master);os.close(slave)

    def test_noninteractive_migration_requires_explicit_flag(self):
        with patch.object(d,'startup_lock',return_value=contextlib.nullcontext()),patch.object(d,'preflight',return_value=([],Path('/tmp/old-data'),'127.0.0.1')),patch.object(d.storage_paths,'choose_path',return_value=Path('/tmp/new-data')),patch.object(d,'run') as run,patch.object(d.storage_paths,'relocate') as relocate,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'--migrate-data'):d.up(self.args(data_dir='/tmp/new-data'))
            run.assert_not_called();relocate.assert_not_called()

    def test_failed_migration_restarts_original_service(self):
        with patch.object(d,'startup_lock',return_value=contextlib.nullcontext()),patch.object(d,'preflight',return_value=([{'id':'old'}],Path('/tmp/old-data'),'127.0.0.1')),patch.object(d.storage_paths,'choose_path',return_value=Path('/tmp/new-data')),patch.object(d,'configure_tailscale',return_value=None),patch.object(d,'run') as run,patch.object(d.storage_paths,'relocate',side_effect=RuntimeError('copy failed')),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'copy failed'):d.up(self.args(data_dir='/tmp/new-data',migrate_data=True))
            commands=[c.args[0] for c in run.call_args_list]
            self.assertEqual([c[len(d.COMPOSE)] for c in commands],['build','down','up'])
            self.assertIn('--wait',commands[-1])

    def test_host_checks_report_network_failure_without_hiding_it(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as folder,patch.object(d.urllib.request,'urlopen',side_effect=urllib.error.URLError('offline')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.real_host_checks(Path(folder))
            text=output.getvalue()
            self.assertIn('[OK] Storage write/fsync',text)
            self.assertEqual(text.count('[WARN]'),3)
            self.assertIn('Google/Yahoo RSS',text)
            self.assertIn('Docker registry',text)

    def test_launcher_messages_are_english(self):
        import re
        for name in ['scripts/launch.py','scripts/docker_launch.py','scripts/storage_paths.py','run.sh']:
            self.assertIsNone(re.search('[\u4e00-\u9fff]',(d.ROOT/name).read_text()),name)
