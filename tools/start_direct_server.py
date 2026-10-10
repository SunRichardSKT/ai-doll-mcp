"""One-click LAN server; runtime, ownership and browser connection are automatic."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from private_storage import write_json
from owned_processes import launch, terminate, alive
from service_lifecycle import ServiceLease,ServiceAlreadyRunning
from direct_server import DirectServer

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'build/direct-server'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def lan_ip():
    # Use the saved device's route on a PC with both Wi-Fi and Ethernet.
    connection = ROOT / 'build/device-lab/connection-private.json'
    try:
        peer = json.loads(connection.read_text(encoding='utf-8-sig')).get('device_host','').split(':')[0]
    except (OSError, ValueError):
        peer = ''
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect((peer or '192.168.1.1', 80))
            return probe.getsockname()[0]
        except OSError:
            return '127.0.0.1'


def status(base, token):
    request = urllib.request.Request(base + '/api/server', headers={'Authorization':'Bearer '+token})
    with OPENER.open(request, timeout=2) as response:
        return json.load(response)


def _ensure(port=8781, stop=False):
    base = f'http://127.0.0.1:{port}'
    with ServiceLease(FOLDER/'launch.lock'):
        config = FOLDER/'setup-private.json'
        saved = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
        public = saved.get('server_url') if saved.get('manual_address') else f'http://{lan_ip()}:{port}'
        app = DirectServer(FOLDER, public)
        token = app.admin_token
        identity = hashlib.sha256(('installation:' + token).encode()).hexdigest()
        app.close()
        try:
            live = status(base, token)
        except (OSError, ValueError):
            live = None
        if live and live.get('installation_id') != identity:
            raise ValueError('This port belongs to another server')
        if stop:
            if live:
                request = urllib.request.Request(base+'/api/server/stop',data=b'{}',
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                with OPENER.open(request,timeout=3) as response:
                    json.load(response)
            return dict(running=False,local_url=base)
        if not live:
            # Refuse any unrelated listener, including a server without our identity endpoint.
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1',port)) == 0:
                    raise ValueError('The server port is occupied')
            command=[sys.executable,'-X','utf8',str(ROOT/'tools/direct_server.py'),
                '--data-dir',str(FOLDER),'--listen','0.0.0.0','--port',str(port),
                '--public-url',public,'--origin',base,'--local-setup']
            child,owner=launch(command,cwd=ROOT)
            write_json(FOLDER/'process-private.json',owner)
            try:
                deadline=time.monotonic()+15
                while True:
                    try:
                        live=status(base,token)
                        if live.get('installation_id')!=identity:raise ValueError('Wrong server identity')
                        break
                    except OSError:
                        if not alive(owner) or time.monotonic()>=deadline:raise RuntimeError('Server startup timed out')
                        time.sleep(.2)
            except Exception:
                terminate(owner)
                raise
        if not saved.get('manual_address') and live['server_url']!=public:
            request=urllib.request.Request(base+'/api/server/configure',
                data=json.dumps(dict(server_url=public,manual=False)).encode(),
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with OPENER.open(request,timeout=3) as response:live.update(json.load(response))
        write_json(config,dict(server_url=live['server_url'],port=port,manual_address=bool(saved.get('manual_address'))))
        # The fragment is consumed locally by the browser and removed before any request.
        return dict(running=True,local_url=base,server_url=live['server_url'],browser_url=base+'/#connect='+token)


def ensure(port=8781,stop=False):
    deadline=time.monotonic()+30
    while True:
        try:return _ensure(port,stop)
        except ServiceAlreadyRunning:
            if time.monotonic()>=deadline:raise RuntimeError('Server setup is still busy') from None
            time.sleep(.3)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8781)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--stop',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('port must be 1024..65535')
    result=ensure(args.port,args.stop)
    if result['running'] and not args.no_browser:webbrowser.open(result['browser_url'])
    print(json.dumps({k:v for k,v in result.items() if k!='browser_url'},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError):
        raise SystemExit('服务端未启动：检查完整软件包、可写目录和端口占用；已有记录不会清空。')
