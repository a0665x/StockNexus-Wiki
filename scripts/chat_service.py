"""Host-side chat process control; authentication never enters the image."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]

def manage(action,data=None):
    if action not in ('start','stop','status'):raise ValueError('Use ./run.sh chat setup|start|stop|status')
    data=Path(data or os.environ.get('ATLAS_DATA_DIR',ROOT/'data')).resolve()
    private=data/'private';private.mkdir(parents=True,exist_ok=True,mode=0o700)
    pidfile=private/'chat-process.json'
    record=json.loads(pidfile.read_text()) if pidfile.exists() else {}
    pid=record.get('pid');running=False
    if isinstance(pid,int):
        try:running=str(ROOT/'chat/service.mjs').encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
        except OSError:pass
    if action=='status':print('Chat: '+('running' if running else 'stopped'));return
    if action=='stop':
        if running:
            os.kill(pid,signal.SIGTERM)
            for _ in range(40):
                if not Path(f'/proc/{pid}').exists():break
                time.sleep(.05)
        pidfile.unlink(missing_ok=True);return
    if running:return
    node=shutil.which('node')
    if not node or not (ROOT/'node_modules/@openai/codex-sdk').is_dir():raise RuntimeError('Chat needs Node.js 20+. From the repository folder run ./run.sh chat setup, then ./run.sh chat start.')
    env=os.environ.copy();env['ATLAS_CHAT_SOCKET']=str(private/'chat.sock')
    with (private/'chat.log').open('ab') as log:
        child=subprocess.Popen([node,str(ROOT/'chat/service.mjs')],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    pidfile.write_text(json.dumps({'pid':child.pid}));pidfile.chmod(0o600)
    for _ in range(50):
        if child.poll() is not None:raise RuntimeError('Chat failed to start; see data/private/chat.log')
        if (private/'chat.sock').exists():print('Chat: ready');return
        time.sleep(.1)
    raise RuntimeError('Chat startup timed out')

if __name__=='__main__':manage(sys.argv[1] if len(sys.argv)>1 else 'start')
