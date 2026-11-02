#!/usr/bin/env python3
"""Terminal launcher: arrow-key setup, reserved HTTP port, scoped foreground Serve."""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def port_number(text):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError('Port must be an integer from 1 to 65535') from None
    if not 1 <= value <= 65535:
        raise argparse.ArgumentTypeError('Port must be an integer from 1 to 65535')
    return value


def read_key(fd):
    key = os.read(fd, 1)
    if not key:
        raise EOFError('Terminal input closed')
    if key == b'\x1b':
        # Accept both normal cursor keys (CSI) and application cursor keys (SS3).
        if not select.select([fd], [], [], .15)[0]:
            return 'cancel'
        prefix = os.read(fd, 1)
        if prefix in (b'[', b'O') and select.select([fd], [], [], .15)[0]:
            return {b'C': 'right', b'D': 'left'}.get(os.read(fd, 1), '')
        return ''
    if key == b'\x04':
        return 'cancel'
    if key in (b'\r', b'\n'):
        return 'enter'
    if key == b'\x03':
        raise KeyboardInterrupt
    return {b'q': 'cancel', b'h': 'left', b'l': 'right'}.get(key, '')


def choose(label, options, initial=0):
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    index = initial
    print('\n' + label + '  (Left/Right: select · Enter: confirm · q: cancel)', flush=True)
    try:
        tty.setcbreak(fd)
        sys.stdout.write('\033[?25l')
        while True:
            line = '   '.join(f'\033[1;36m[ {item} ]\033[0m' if i == index else str(item)
                              for i, item in enumerate(options))
            sys.stdout.write('\r\033[2K' + line)
            sys.stdout.flush()
            key = read_key(fd)
            if key == 'enter':
                return index
            if key == 'cancel':
                raise KeyboardInterrupt
            if key in ('left', 'right'):
                index = (index + (1 if key == 'right' else -1)) % len(options)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write('\033[0m\033[?25h\n')
        sys.stdout.flush()


def available(port, host='0.0.0.0'):
    """Match the HTTP server's bind semantics; surface permission errors distinctly."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
            probe.listen(1)
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                return False
            if error.errno in (errno.EACCES, errno.EPERM) and port < 1024:
                return False
            raise
    return True


def candidates(preferred, host, excluded=(), count=4):
    found = []
    # Search nearby first, then well-known development ports; never suggest a used port.
    pool = [preferred] + list(range(max(1024, preferred + 1), min(65536, preferred + 65)))
    pool += [8765, 8766, 8767, 8000, 8080, 8888, 9000, 9443, 10000]
    for port in dict.fromkeys(pool):
        if port not in excluded and available(port, host):
            found.append(port)
            if len(found) >= count:
                break
    return found


def choose_port(label, preferred, host, excluded=(), interactive=True):
    while True:
        if not interactive:
            if preferred in excluded or not available(preferred, host):
                raise RuntimeError(f'{label} {preferred} is occupied or unavailable; specify another port.')
            return preferred
        options = candidates(preferred, host, excluded)
        if preferred not in options:
            print(f'{label} {preferred} is occupied or unavailable; choose another port.', flush=True)
        selected = choose(label, [str(p) for p in options] + ['Custom port'])
        if selected < len(options):
            return options[selected]
        try:
            preferred = port_number(input('Enter port (1-65535): ').strip())
        except argparse.ArgumentTypeError as error:
            print(error)


def tailscale_json(*arguments):
    try:
        result = subprocess.run(['tailscale', *arguments], capture_output=True, text=True,
                                timeout=5, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Tailscale status timed out; check tailscale status.') from None
    if result.returncode:
        raise RuntimeError('Tailscale unavailable: ' + (result.stderr.strip() or result.stdout.strip()))
    try:
        return json.loads(result.stdout) or {}
    except ValueError:
        raise RuntimeError('Invalid Tailscale status; check tailscale status.') from None


def tailnet_name():
    if not shutil.which('tailscale'):
        raise RuntimeError('Tailscale not found; install and sign in, or choose Local.')
    state = tailscale_json('status', '--json')
    if state.get('BackendState') != 'Running':
        raise RuntimeError('Tailscale is not connected; sign in or choose Local.')
    name = (state.get('Self', {}).get('DNSName') or '').rstrip('.')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', name):
        raise RuntimeError('Tailscale has no HTTPS hostname; check MagicDNS/HTTPS settings.')
    return name


def serve_ports(config):
    """Includes Foreground sessions and existing Services as well as background entries."""
    ports = set()
    if isinstance(config, dict):
        for key in config.get('TCP', {}) or {}:
            if str(key).isdigit():
                ports.add(int(key))
        for field in ('Web', 'AllowFunnel'):
            for key in config.get(field, {}) or {}:
                end = str(key).rsplit(':', 1)[-1]
                if end.isdigit():
                    ports.add(int(end))
        for child in config.values():
            ports.update(serve_ports(child))
    elif isinstance(config, list):
        for child in config:
            ports.update(serve_ports(child))
    return ports


def serves(config, name, port, target):
    if isinstance(config, dict):
        web = (config.get('Web') or {}).get(f'{name}:{port}', {})
        if (web.get('Handlers') or {}).get('/', {}).get('Proxy') == target:
            return True
        return any(serves(child, name, port, target) for child in config.values())
    if isinstance(config, list):
        return any(serves(child, name, port, target) for child in config)
    return False


def make_server(host, port):
    sys.path.insert(0, str(ROOT))
    from server import Handler, ThreadingHTTPServer
    # Reserve the chosen port before initializing the DB or configuring Serve.
    return ThreadingHTTPServer((host, port), Handler)


def stop_process(process):
    if process and process.poll() is None:
        try:
            process.terminate()
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_server(httpd, mode, name=None, https_port=None):
    proxy = None
    worker = None
    try:
        from news_atlas.storage import Store
        httpd.store = Store()
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        port = httpd.server_address[1]
        local_url = f'http://127.0.0.1:{port}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(local_url + '/api/status', timeout=5) as response:
            if response.status != 200:
                raise RuntimeError('Local service failed to start.')
        url = local_url
        if mode == 'tailscale':
            # Foreground Serve is tied to this child process. No --bg, reset, or global off.
            if https_port in serve_ports(tailscale_json('serve', 'status', '--json')):
                raise RuntimeError(f'Tailscale HTTPS {https_port} is occupied by another service; choose another port.')
            print('Starting Tailscale HTTPS; follow any authorization link shown.', flush=True)
            proxy = subprocess.Popen(['tailscale', 'serve', f'--https={https_port}', local_url],
                                     stdin=subprocess.DEVNULL, start_new_session=True)
            deadline = time.monotonic() + 30
            while True:
                if proxy.poll() is not None:
                    raise RuntimeError('Tailscale Serve exited; check the permission/HTTPS messages above.')
                if serves(tailscale_json('serve', 'status', '--json'), name, https_port, local_url):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Tailscale HTTPS is not ready; complete setup and retry.')
                time.sleep(.25)
            url = f'https://{name}' + (f':{https_port}' if https_port != 443 else '')
        print(f'\n✓ GraphNews started\nURL: {url}', flush=True)
        if mode == 'tailscale':
            print(f'Local: {local_url}\nTailscale devices must use the same tailnet.', flush=True)
        else:
            print(f'LAN: http://<host-LAN-IP>:{port}', flush=True)
        print('Press Ctrl+C to stop this service.', flush=True)
        while worker.is_alive():
            if proxy and proxy.poll() is not None:
                raise RuntimeError('Tailscale Serve stopped; stopping this local service.')
            time.sleep(.25)
        raise RuntimeError('HTTP service stopped.')
    finally:
        try:
            stop_process(proxy)
        finally:
            try:
                if worker and worker.is_alive():
                    httpd.shutdown()
                    worker.join(timeout=3)
            finally:
                httpd.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='run.sh', description='GraphNews: select mode and port with arrow keys; Enter to start.')
    parser.add_argument('--port', type=port_number, default=os.environ.get('PORT', '8765'), help='Local HTTP port; default 8765 or PORT')
    parser.add_argument('--mode', choices=['local', 'tailscale'], default='local', help='Initial startup mode')
    parser.add_argument('--https-port', type=port_number, default=8443, help='Tailscale HTTPS port; default 8443')
    parser.add_argument('--non-interactive', action='store_true', help='Use specified settings; report conflicts without changing ports')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error('Python 3.10 or newer is required')
    interactive = not args.non_interactive
    if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error('Interactive setup requires a terminal; for automation use --non-interactive --mode local --port 8765')
    if interactive and os.name != 'posix':
        parser.error('Arrow-key setup requires a Linux/macOS/WSL terminal')
    print('GraphNews startup configuration', flush=True)
    while True:
        mode = ['local', 'tailscale'][choose('Startup mode', ['Local', 'Tailscale HTTPS'], args.mode == 'tailscale')] if interactive else args.mode
        name = None
        if mode == 'tailscale':
            try:
                name = tailnet_name()
            except RuntimeError as error:
                if not interactive:
                    raise
                print(str(error), flush=True)
                args.mode = 'local'
                continue
        host = '127.0.0.1' if mode == 'tailscale' else '0.0.0.0'
        port = choose_port('Local HTTP port', args.port, host, interactive=interactive)
        https_port = None
        if mode == 'tailscale':
            occupied = serve_ports(tailscale_json('serve', 'status', '--json')) | {port}
            https_port = choose_port('Tailscale HTTPS port', args.https_port, '0.0.0.0', occupied, interactive)
        print(f'\nSettings: {mode} · HTTP {port}' + (f' · HTTPS {https_port}' if https_port else ''), flush=True)
        if interactive:
            action = choose('Confirm settings', ['Start', 'Reconfigure', 'Cancel'])
            if action == 1:
                continue
            if action == 2:
                print('Cancelled; service was not started.')
                return 0
        try:
            httpd = make_server(host, port)
        except OSError as error:
            if error.errno == errno.EADDRINUSE and interactive:
                print(f'HTTP {port} was just claimed by another process; choose another port.', flush=True)
                args.port = port
                args.mode = mode
                continue
            raise
        run_server(httpd, mode, name, https_port)
        return 0


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, interrupted)
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nStopped/cancelled.', flush=True)
        sys.exit(130)
    except (OSError, RuntimeError) as error:
        print(f'\nStartup failed: {error}', file=sys.stderr)
        sys.exit(1)
