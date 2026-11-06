#!/usr/bin/env python3
"""One fixed Compose project/port, serialized reconciliation and optional host Serve."""
from __future__ import annotations
import argparse
import contextlib
import concurrent.futures
import ssl
import urllib.error
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    from . import launch, storage_paths, chat_service
except ImportError:
    import launch
    import storage_paths
    import chat_service

ROOT=Path(__file__).resolve().parents[1]
PROJECT='news-atlas'
PORT=8765
LOCAL='http://127.0.0.1:8765'
COMPOSE=['docker','compose','--project-directory',str(ROOT),'-f',str(ROOT/'compose.yaml'),'-p',PROJECT]


def run(args, capture=False):
    result=subprocess.run(args, text=True, capture_output=capture, check=False)
    if result.returncode:
        raise RuntimeError((result.stderr.strip() if capture else '') or f'Command failed (exit {result.returncode}): '+ ' '.join(args[:4]))
    return result.stdout.strip() if capture else ''


def json_run(args):
    return json.loads(run(args,True))


@contextlib.contextmanager
def startup_lock():
    # Same host port across different checkouts and COMPOSE_PROJECT_NAME values.
    path=Path(tempfile.gettempdir())/'news-atlas-docker-8765.lock'
    with path.open('a') as file:
        try:fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another News Atlas start/stop process is running; wait for it to finish.') from None
        try:yield
        finally:fcntl.flock(file,fcntl.LOCK_UN)


def containers():
    ids=run(['docker','ps','-aq','--filter',f'label=com.docker.compose.project={PROJECT}'],True).split()
    if not ids:return []
    template='{"id":{{json .Id}},"state":{{json .State}},"labels":{{json .Config.Labels}},"ports":{{json .NetworkSettings.Ports}}}'
    return [json.loads(line) for line in run(['docker','inspect','--format',template,*ids],True).splitlines()]


def preflight():
    print('[CHECK] Docker CLI / Compose / daemon...',flush=True)
    print('[OK] '+run(['docker','compose','version'],True),flush=True)
    print('[OK] Docker daemon '+run(['docker','info','--format','{{.ServerVersion}}'],True),flush=True)
    config=json_run(COMPOSE+['config','--format','json'])
    service=config['services']['atlas']
    ports=service.get('ports',[])
    if len(ports)!=1 or str(ports[0].get('published'))!='8765' or ports[0].get('target')!=8765:
        raise RuntimeError('Compose must map host 8765 to container 8765.')
    bind=ports[0].get('host_ip','0.0.0.0')
    if bind not in ('127.0.0.1','0.0.0.0'):
        raise RuntimeError('ATLAS_BIND must be 127.0.0.1 or 0.0.0.0 for consistent local/Tailscale access.')
    data=next(v['source'] for v in service['volumes'] if v['target']=='/app/data')
    if not Path(data).is_dir():raise RuntimeError('Data directory does not exist: '+data)
    own=containers()
    for container in own:
        directory=container['labels'].get('com.docker.compose.project.working_dir')
        if directory and Path(directory).resolve()!=ROOT:
            raise RuntimeError('Project news-atlas is managed by another directory: '+directory+'; stop it from that directory before changing the data source.')
    # The native bind probe catches non-Docker processes too; never kill that owner.
    running=any(c['state']['Running'] and any(b.get('HostPort')=='8765' for b in (c['ports'] or {}).get('8765/tcp') or []) for c in own)
    outsiders=set(run(['docker','ps','-q','--filter','publish=8765'],True).split())
    ownids={c['id'] for c in own}
    if any(not any(full.startswith(short) for full in ownids) for short in outsiders):
        raise RuntimeError('Port 8765 is occupied by another container; no changes made.')
    if not running and not launch.available(PORT,bind):
        raise RuntimeError('Port 8765 is occupied by another process; stop it before retrying.')
    print(f'[OK] Project ownership: {PROJECT}; {len(own)} existing container(s).',flush=True)
    for container in own:print('[INFO] Container '+container['id'][:12]+': '+container['state'].get('Status','unknown')+' / '+container['state'].get('Health',{}).get('Status','no health status'),flush=True)
    print(f'[OK] Port ownership: {bind}:8765 -> 8765; no foreign owner.',flush=True)
    return own,Path(data),bind


def host_checks(data):
    if sys.version_info < (3,10):raise RuntimeError('Python 3.10 or newer is required.')
    print('[OK] Python '+sys.version.split()[0],flush=True)
    usage=shutil.disk_usage(data)
    print(f'[OK] Storage: {data}; free {usage.free/1024**3:.1f} GiB; mount {storage_paths.mountpoint(data)}',flush=True)
    try:
        with tempfile.TemporaryFile(dir=data) as probe:
            probe.write(b'News Atlas storage check');probe.flush();os.fsync(probe.fileno())
    except OSError as error:raise RuntimeError('Storage write/fsync check failed: '+str(error)) from None
    print('[OK] Storage write/fsync; existing data retained.',flush=True)
    print('[CHECK] Network: DNS, TLS and HTTPS reachability (no credentials sent).',flush=True)
    endpoints=[('Google/Yahoo RSS','https://news.google.com/rss/'),('Massive API','https://api.massive.com/'),('Docker registry','https://registry-1.docker.io/v2/')]
    def check(item):
        label,url=item
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'NewsAtlas-preflight/1.0'})
            with urllib.request.urlopen(req,timeout=4) as response:status=response.status
        except urllib.error.HTTPError as error:status=error.code
        except (OSError,urllib.error.URLError,ssl.SSLError):return f'[WARN] {label}: DNS/TLS/HTTPS unavailable or timed out. Cached/local use can continue.'
        return f'[OK] {label}: HTTPS reachable, HTTP {status} (reachability only; account/data access not tested).'
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(check,endpoints):print(result,flush=True)


def configure_tailscale(args, interactive):
    if not shutil.which('tailscale'):
        if args.tailscale=='on':raise RuntimeError('Tailscale not found; cannot enable HTTPS.')
        print('[SKIP] Tailscale is not installed; no prompt or configuration.',flush=True)
        return None
    print('[CHECK] Tailscale installed; checking connection status.',flush=True)
    try:name=launch.tailnet_name()
    except RuntimeError as error:
        if args.tailscale=='on':raise
        print(str(error)+'; starting local service only.',flush=True)
        return None
    enable=args.tailscale=='on'
    if args.tailscale=='auto' and interactive:
        enable=launch.choose('Enable Tailscale HTTPS?', ['Local only','Enable'])==1
    if not enable:
        print('[OK] No new Tailscale configuration; existing routes retained.',flush=True)
        return None
    state=launch.tailscale_json('serve','status','--json')
    if args.https_port in launch.serve_ports(state) and not launch.serves(state,name,args.https_port,LOCAL):
        raise RuntimeError(f'Tailscale HTTPS {args.https_port} is already in use; choose an unused --https-port.')
    return name,args.https_port


def marker_path(data):return data/'private'/'docker-serve.json'


def enable_tailscale(target,data):
    name,port=target
    marker=marker_path(data)
    if marker.exists():
        previous=json.loads(marker.read_text())
        if (previous.get('name'),previous.get('port'))!=(name,port):
            stop_owned_tailscale(data)
            if marker.exists():raise RuntimeError('Existing project route contains additional settings; no second route added.')
    state=launch.tailscale_json('serve','status','--json')
    if launch.serves(state,name,port,LOCAL):
        print('[OK] Reusing the existing Tailscale route.',flush=True)
    else:
        if port in launch.serve_ports(state):raise RuntimeError('Tailscale HTTPS port was claimed by another service; not overwritten.')
        # Record intent first so down can recover even if the CLI is interrupted.
        marker=marker_path(data);marker.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        marker.write_text(json.dumps({'name':name,'port':port,'target':LOCAL}));marker.chmod(0o600)
        run(['tailscale','serve','--bg',f'--https={port}',LOCAL])
        deadline=time.monotonic()+15
        while not launch.serves(launch.tailscale_json('serve','status','--json'),name,port,LOCAL):
            if time.monotonic()>deadline:raise RuntimeError('Tailscale proxy not ready; check permissions and HTTPS settings.')
            time.sleep(.25)
    return f'https://{name}'+(f':{port}' if port!=443 else '')


def stop_owned_tailscale(data):
    marker=marker_path(data)
    if not marker.exists():return
    if not shutil.which('tailscale'):
        print('Tailscale not installed; proxy ownership record retained.');return
    info=json.loads(marker.read_text());state=launch.tailscale_json('serve','status','--json')
    name,port=info['name'],info['port']
    # Only our exact background root mapping; do not remove extra handlers/foreground sessions.
    handlers=(state.get('Web',{}).get(f'{name}:{port}',{})).get('Handlers',{})
    if handlers=={'/':{'Proxy':LOCAL}} and info.get('target')==LOCAL:
        run(['tailscale','serve',f'--https={port}','off']);marker.unlink()
        print('Stopped the Tailscale route owned by this launcher.')
    elif not launch.serves(state,name,port,LOCAL):marker.unlink()
    else:print('Tailscale route contains other settings; retained without global reset.')


def up(args):
    interactive=not args.non_interactive and sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:print('Non-interactive mode: no menus; no new Tailscale route by default.',flush=True)
    with startup_lock():
        print('[1/4] Preflight: Docker, project news-atlas, port 8765, storage and network...',flush=True)
        own,data,bind=preflight()
        host_checks(data)
        selected=storage_paths.choose_path(data,interactive,launch.choose,getattr(args,'data_dir',None))
        changing=selected!=data.resolve()
        if changing and not interactive and not getattr(args,'migrate_data',False):
            raise RuntimeError('Non-interactive relocation requires --migrate-data; data unchanged.')
        target=configure_tailscale(args,interactive)
        if interactive and launch.choose('Confirm startup: HTTP 8765'+(' + Tailscale HTTPS' if target else '')+('; relocate data to '+str(selected) if changing else ''),['Start/update','Cancel'])==1:
            print('Cancelled; containers unchanged.');return 0
        print('[2/4] Building image (cached layers reused; build failure keeps current service)...',flush=True)
        run(COMPOSE+['build'])
        if changing:
            print('Stopping project containers; verifying and relocating data...',flush=True)
            chat_service.manage('stop',data)
            run(COMPOSE+['down','--remove-orphans'])
            try:data=storage_paths.relocate(ROOT,data,selected)
            except BaseException:
                print('Relocation failed; original data retained. Restoring original service.',flush=True)
                if own:run(COMPOSE+['up','-d','--no-build','--wait','--scale','atlas=1'])
                raise
            os.environ['ATLAS_DATA_DIR']=str(data);own=[]
        print('Data mount: '+str(data)+' → /app/data',flush=True)
        healthy=len(own)==1 and own[0]['state'].get('Running') is True and own[0]['labels'].get('com.docker.compose.service')=='atlas' and own[0]['state'].get('Health',{}).get('Status')=='healthy'
        if own and not healthy:
            print('[3/4] Cleaning project stale/unhealthy/duplicate containers; data retained.',flush=True)
            run(COMPOSE+['down','--remove-orphans'])
            if not launch.available(PORT,bind):raise RuntimeError('Port 8765 was claimed after cleanup; no new container started.')
        else:
            print('[3/4] '+('One healthy container exists; reuse if image/config unchanged; no duplicates.' if own else 'Clean state; starting one container.'),flush=True)
        try:
            run(COMPOSE+['up','-d','--no-build','--wait','--wait-timeout','90','--remove-orphans','--scale','atlas=1'])
            final=containers()
            if len(final)!=1 or final[0]['state'].get('Health',{}).get('Status')!='healthy':raise RuntimeError('Container count or health violates the single-service requirement.')
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(LOCAL+'/api/status',timeout=5) as response:
                if response.status!=200:raise RuntimeError('Host port 8765 health check failed.')
        except BaseException:
            print('Startup failed; cleaning project containers, retaining data/.',flush=True)
            run(COMPOSE+['down','--remove-orphans'])
            raise
        try:chat_service.manage('start',data)
        except (OSError,RuntimeError) as error:print('[WARN] '+str(error),flush=True)
        print('[4/4] [OK] One healthy container; fixed HTTP 8765 -> 8765.\nURL: '+LOCAL,flush=True)
        if bind=='0.0.0.0':print('LAN URL: http://<host-LAN-IP>:8765',flush=True)
        if target:
            try:print('Tailscale URL: '+enable_tailscale(target,data),flush=True)
            except (OSError,RuntimeError) as error:
                print('Tailscale setup failed: '+str(error)+'\nLocal container is healthy. URL: '+LOCAL,flush=True)
                return 1
        print(merge_help(data),flush=True)
        print('Running in background. Status: ./run.sh status | Logs: ./run.sh logs | Stop: ./run.sh down',flush=True)
    return 0



def merge_help(data):
    command=shlex.quote(str(ROOT/'merge_data.sh'))+' --from /media/usb/data --to '+shlex.quote(str(data))
    return ('Import USB data from another terminal (replace /media/usb/data):\n'
            '  Preview: '+command+' --dry-run\n'
            '  Merge:   '+command+'\n'
            'Keep this web service open; pause Wiki work/watchers for stocks being merged.\n'
            'The Saved Wikis menu refreshes automatically within 6 seconds; choose an imported stock to view it.\n'
            'Details: spec/DATA_MERGE.md')


def main(argv=None):
    parser=argparse.ArgumentParser(description='Docker launcher: fixed news-atlas project and port 8765')
    parser.add_argument('action',choices=['up','down','build','restart','logs','status'])
    parser.add_argument('--non-interactive',action='store_true')
    parser.add_argument('--tailscale',choices=['auto','on','off'],default='auto')
    parser.add_argument('--data-dir',help='Absolute path to a custom data directory')
    parser.add_argument('--migrate-data',action='store_true',help='Allow non-interactive data relocation, retaining a backup')
    parser.add_argument('--https-port',type=launch.port_number,default=8443)
    args=parser.parse_args(argv)
    if args.action not in ('status','logs'):
        if args.action=='down' and (ROOT/storage_paths.STATE).exists():
            # Stopping must still work if a removable data disk is absent.
            recorded=json.loads((ROOT/storage_paths.STATE).read_text())
            os.environ['ATLAS_DATA_DIR']=recorded['data_dir']
        else:
            saved_data=storage_paths.load(ROOT)
            if saved_data is not None:os.environ['ATLAS_DATA_DIR']=str(saved_data)
    if args.action=='up':return up(args)
    if args.action in ('status','logs'):
        run(COMPOSE+(['ps'] if args.action=='status' else ['logs','--tail','100','-f']));return 0
    with startup_lock():
        if args.action=='down':
            config=json_run(COMPOSE+['config','--format','json'])
            data=Path(next(v['source'] for v in config['services']['atlas']['volumes'] if v['target']=='/app/data'))
            run(COMPOSE+['down','--remove-orphans']);stop_owned_tailscale(data);chat_service.manage('stop',data)
            print('[OK] Project stopped; data retained.')
        elif args.action=='build':run(COMPOSE+['build'])
        else:
            run(COMPOSE+['restart']);run(COMPOSE+['up','-d','--no-build','--wait','--scale','atlas=1'])
            print('[OK] Restarted. URL: '+LOCAL)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (KeyboardInterrupt,EOFError):print('\nCancelled.');sys.exit(130)
    except (RuntimeError,OSError,ValueError) as error:print('Startup failed: '+str(error),file=sys.stderr);sys.exit(1)
