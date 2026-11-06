import argparse
import contextlib
import errno
import io
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from scripts import launch


class LauncherTests(unittest.TestCase):
    def test_port_validation_and_free_candidates(self):
        for value in ['0', '-1', '65536', 'abc', '3.5']:
            with self.assertRaises(argparse.ArgumentTypeError):
                launch.port_number(value)
        self.assertEqual(launch.port_number('65535'), 65535)
        with patch.object(launch, 'available', side_effect=lambda p, h: p not in {8765, 8767}):
            self.assertEqual(launch.candidates(8765, '0.0.0.0', {8768}), [8766, 8769, 8770, 8771])
            with self.assertRaises(RuntimeError):
                launch.choose_port('HTTP', 8765, '0.0.0.0', interactive=False)
        with patch.object(launch, 'available', return_value=True):
            ports = launch.candidates(65535, '0.0.0.0')
            self.assertTrue(all(1 <= p <= 65535 for p in ports))
            self.assertEqual(ports[0], 65535)

    def test_busy_port_is_not_a_permission_failure(self):
        probe = MagicMock()
        probe.__enter__.return_value = probe
        with patch.object(launch.socket, 'socket', return_value=probe):
            probe.bind.side_effect = OSError(errno.EADDRINUSE, 'busy')
            self.assertFalse(launch.available(8765))
            probe.bind.side_effect = PermissionError(errno.EPERM, 'sandbox')
            with self.assertRaises(PermissionError):
                launch.available(8765)
        probe.close.assert_not_called()  # Context manager owns cleanup.
        self.assertTrue(probe.__exit__.called)

    def test_custom_port_and_collision(self):
        with patch.object(launch, 'available', side_effect=lambda p, h: p != 9001), \
             patch.object(launch, 'choose', side_effect=[4, 4, 0]), \
             patch('builtins.input', side_effect=['invalid', '9001']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launch.choose_port('HTTP', 8765, '0.0.0.0'), 9002)

    def test_foreground_and_background_serve_scopes(self):
        config = {'TCP': {'443': {}}, 'Foreground': {'session': {
            'TCP': {'8443': {}}, 'Web': {'test.tail.ts.net:8443': {
                'Handlers': {'/': {'Proxy': 'http://127.0.0.1:8765'}}}}}},
            'Services': {'svc:test': {'TCP': {'9443': {}}}}, 'AllowFunnel': {'test.tail.ts.net:10443': True}}
        self.assertEqual(launch.serve_ports(config), {443, 8443, 9443, 10443})
        self.assertTrue(launch.serves(config, 'test.tail.ts.net', 8443, 'http://127.0.0.1:8765'))
        self.assertFalse(launch.serves(config, 'test.tail.ts.net', 8443, 'http://127.0.0.1:9000'))
        self.assertFalse(launch.serves({}, 'test.tail.ts.net', 8443, 'http://127.0.0.1:8765'))

    def test_tailscale_requirements(self):
        with patch.object(launch.shutil, 'which', return_value=None), self.assertRaisesRegex(RuntimeError, 'not found'):
            launch.tailnet_name()
        with patch.object(launch.shutil, 'which', return_value='/bin/tailscale'), \
             patch.object(launch, 'tailscale_json', return_value={'BackendState': 'NeedsLogin'}), \
             self.assertRaisesRegex(RuntimeError, 'not connected'):
            launch.tailnet_name()
        with patch.object(launch.shutil, 'which', return_value='/bin/tailscale'), \
             patch.object(launch, 'tailscale_json', return_value={'BackendState': 'Running', 'Self': {'DNSName': 'test.tail.ts.net.'}}):
            self.assertEqual(launch.tailnet_name(), 'test.tail.ts.net')

    def test_race_reprompts_without_killing_owner(self):
        httpd = MagicMock()
        with patch.object(sys.stdin, 'isatty', return_value=True), patch.object(sys.stdout, 'isatty', return_value=True), \
             patch.object(launch, 'choose', return_value=0), patch.object(launch, 'choose_port', side_effect=[8765, 8766]), \
             patch.object(launch, 'make_server', side_effect=[OSError(errno.EADDRINUSE, 'race'), httpd]) as make, \
             patch.object(launch, 'run_server') as run, contextlib.redirect_stdout(io.StringIO()) as output:
            # redirect_stdout itself is not a tty; substitute its isatty for this controlled scenario.
            output.isatty = lambda: True
            self.assertEqual(launch.main([]), 0)
            self.assertEqual(make.call_args_list[-1].args, ('0.0.0.0', 8766))
            run.assert_called_once_with(httpd, 'local', None, None)
            self.assertIn('was just claimed by another process', output.getvalue())

    def test_setup_cancel_never_binds(self):
        with patch.object(sys.stdin, 'isatty', return_value=True), patch.object(launch, 'choose', side_effect=[0, 2]), \
             patch.object(launch, 'choose_port', return_value=8765), patch.object(launch, 'make_server') as make, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            output.isatty = lambda: True
            self.assertEqual(launch.main([]), 0)
            make.assert_not_called()

    def test_foreground_proxy_ready_url_and_cleanup(self):
        name = 'test.tail.ts.net'
        config = {'Foreground': {'session': {'Web': {name + ':8443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:8766'}}}}}}}
        httpd = MagicMock(server_address=('127.0.0.1', 8766))
        proxy = MagicMock()
        proxy.poll.return_value = None
        response = MagicMock()
        response.__enter__.return_value.status = 200
        worker = MagicMock()
        worker.is_alive.return_value = True
        with patch('news_atlas.graph_storage.GraphRepository'), patch.object(launch.threading, 'Thread', return_value=worker), \
             patch.object(launch.urllib.request, 'build_opener') as opener, \
             patch.object(launch, 'tailscale_json', side_effect=[{}, config]), \
             patch.object(launch.subprocess, 'Popen', return_value=proxy) as popen, \
             patch.object(launch.time, 'sleep', side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()) as output:
            opener.return_value.open.return_value = response
            with self.assertRaises(KeyboardInterrupt):
                launch.run_server(httpd, 'tailscale', name, 8443)
            self.assertIn('URL: https://test.tail.ts.net:8443', output.getvalue())
            self.assertEqual(popen.call_args.args[0], ['tailscale', 'serve', '--https=8443', 'http://127.0.0.1:8766'])
            proxy.terminate.assert_called_once()
            httpd.shutdown.assert_called_once()
            httpd.server_close.assert_called_once()

    def test_proxy_failure_closes_http_and_child(self):
        httpd = MagicMock(server_address=('127.0.0.1', 8765))
        proxy = MagicMock()
        proxy.poll.return_value = 1
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch('news_atlas.graph_storage.GraphRepository'), patch.object(launch.threading, 'Thread'), \
             patch.object(launch.urllib.request, 'build_opener') as opener, patch.object(launch, 'tailscale_json', return_value={}), \
             patch.object(launch.subprocess, 'Popen', return_value=proxy), contextlib.redirect_stdout(io.StringIO()):
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(RuntimeError, 'Serve exited'):
                launch.run_server(httpd, 'tailscale', 'test.tail.ts.net', 8443)
            httpd.shutdown.assert_called_once()
            httpd.server_close.assert_called_once()


@unittest.skipUnless(os.name == 'posix', 'POSIX terminal required')
class TerminalTests(unittest.TestCase):
    def test_real_terminal_arrows_busy_candidates_and_enter(self):
        import pty
        import termios
        master, slave = pty.openpty()
        before = termios.tcgetattr(slave)
        code = """
from scripts import launch
launch.available=lambda port,host: port!=8765
launch.make_server=lambda host,port: (host,port)
launch.run_server=lambda server,*args: print('URL: http://127.0.0.1:'+str(server[1]),flush=True)
raise SystemExit(launch.main([]))
"""
        child = subprocess.Popen([sys.executable, '-u', '-c', code], stdin=slave, stdout=slave, stderr=slave,
                                 cwd=launch.ROOT, start_new_session=True)
        output = bytearray()
        def until(text):
            deadline = time.monotonic() + 5
            while text.encode() not in output:
                if time.monotonic() > deadline:
                    self.fail(output.decode(errors='replace'))
                if select.select([master], [], [], .1)[0]:
                    output.extend(os.read(master, 4096))
        try:
            until('[ Local ]')
            os.write(master, b'\x1b[C\x1b[D\r')
            until('[ 8766 ]')
            os.write(master, b'\x1b[C\r')
            until('[ Start ]')
            os.write(master, b'\r')
            until('URL: http://127.0.0.1:8767')
            self.assertEqual(child.wait(timeout=3), 0)
            self.assertEqual(termios.tcgetattr(slave), before, 'Restore terminal modes after selecting')
            self.assertIn('8765 is occupied', output.decode(errors='replace'))
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
