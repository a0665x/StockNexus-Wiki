"""Local-only HTTP facade for the host SDK bridge over a private Unix socket."""
import http.client
import socket
import urllib.parse
import ipaddress
from pathlib import Path

def local_peer(address):
    if ipaddress.ip_address(address).is_loopback:return True
    try:
        # Docker DNAT presents host-local connections as the default gateway.
        for line in Path('/proc/net/route').read_text().splitlines()[1:]:
            fields=line.split()
            if fields[1]=='00000000' and address==socket.inet_ntoa(bytes.fromhex(fields[2])[::-1]):return True
    except (OSError,ValueError,IndexError):pass
    return False

PATHS={'session','sync','turn','cancel','reset','status'}
class UnixConnection(http.client.HTTPConnection):
    def __init__(self,path):
        super().__init__('localhost',timeout=650);self.path=path
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout);self.sock.connect(str(self.path))

def handle(handler):
    path=urllib.parse.urlsplit(handler.path).path.removeprefix('/api/chat/')
    host=handler.headers.get('Host','')
    origin=handler.headers.get('Origin','')
    # Deliberately local only; do not expose a signed-in account through LAN/Tailscale.
    if not local_peer(handler.client_address[0]) or host not in ('127.0.0.1:8765','localhost:8765') or handler.headers.get('Sec-Fetch-Site')=='cross-site' or (origin and origin!='http://'+host) or (handler.command=='POST' and origin!='http://'+host):
        handler.json_response(403,{'error':'Chat 僅開放本機 http://127.0.0.1:8765，請從該頁面操作。'});return
    if path not in PATHS or (handler.command=='GET')!=(path=='status'):
        handler.json_response(404,{'error':'Unknown chat endpoint'});return
    data=None
    if handler.command=='POST':
        try:
            size=int(handler.headers.get('Content-Length','0'))
            if handler.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<size<=32*1024*1024:raise ValueError()
            data=handler.rfile.read(size)
        except ValueError:
            handler.json_response(400,{'error':'Invalid chat body'});return
    conn=UnixConnection(handler.store.path.parent/'private/chat.sock')
    started=False
    try:
        conn.request(handler.command,'/'+path,body=data,headers={'Content-Type':'application/json','Authorization':handler.headers.get('Authorization','')})
        response=conn.getresponse()
        started=True
        handler.send_response(response.status)
        handler.send_header('Content-Type',response.getheader('Content-Type','application/json'))
        handler.send_header('Cache-Control','no-store');handler.send_header('Connection','close');handler.end_headers();handler.close_connection=True
        while True:
            chunk=response.readline() if path=='turn' else response.read(65536)
            if not chunk:break
            handler.wfile.write(chunk);handler.wfile.flush()
    except (BrokenPipeError,ConnectionResetError):pass
    except OSError:
        if not started:handler.json_response(503,{'error':'Chat 服務未啟動。請執行 ./run.sh chat start。'})
        else:
            try:handler.wfile.write(b'{"error":"Chat service unavailable; run ./run.sh chat start"}\n')
            except OSError:pass
    finally:conn.close()
