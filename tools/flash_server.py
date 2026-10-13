"""Local one-button flasher. All device writes use the verified CLI engine."""
import argparse
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import threading
from types import SimpleNamespace
import webbrowser

from flash_esp32 import ROOT, FlashJob, flash, validate_images, select_port
from service_lifecycle import ExclusiveLoopbackServer, ServiceLease, ServiceAlreadyRunning

PORT = 8770


class Flasher:
    def __init__(self):
        self.csrf = secrets.token_hex(24)
        self.lock = threading.Lock()
        self.job = None
        self.running = False

    def state(self):
        from serial.tools.list_ports import comports
        ports = list(comports())
        try:
            selected = select_port(ports)
        except ValueError:
            selected = ''
        try:
            manifest, _ = validate_images(ROOT/'firmware/prebuilt')
            firmware, image_error = manifest['firmware'], None
        except (ValueError, OSError, KeyError) as error:
            firmware, image_error = None, str(error)
        with self.lock:
            job = self.job
            running = self.running
        report, log = None, ''
        if job:
            try:
                report = json.loads(job.reportfile.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                report = {'status':'running','phase':'prepare'}
            log = job.logfile.read_text(encoding='utf-8', errors='replace')[-16000:]
        return dict(app='ai-doll-flasher', ports=[dict(port=p.device, description=p.description) for p in ports],
                    selected_port=selected, firmware=firmware, image_error=image_error,
                    running=running, report=report, log=log,
                    result_folder=str(job.folder) if job else None)

    def start(self, data):
        if not isinstance(data,dict) or set(data)-{'port','factory','factory_confirmed'}:
            raise ValueError('请求格式不正确。')
        if not isinstance(data.get('port',''),str) or type(data.get('factory',False)) is not bool:
            raise ValueError('串口或烧录方式不正确。')
        if data.get('factory') and data.get('factory_confirmed') is not True:
            raise ValueError('恢复出厂需要勾选清除设备设置确认。')
        with self.lock:
            if self.running:
                raise RuntimeError('正在烧录，请等待完成。')
            self.job = FlashJob()
            self.running = True
            job = self.job
        args = SimpleNamespace(port=data.get('port') or None, baud=460800,
                               images=ROOT/'firmware/prebuilt', factory=data.get('factory',False), boot_timeout=180)
        def worker():
            try:
                flash(args,job)
            finally:
                with self.lock:
                    self.running=False
        threading.Thread(target=worker,daemon=True).start()
        return {'started':True,'flash_id':job.id}


def make_handler(flasher):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            hosts = (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
            return self.headers.get('Host') in hosts and self.headers.get('Origin','') in ('',*('http://'+h for h in hosts))

        def send(self, code, data):
            raw=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.allowed():
                return self.send(403,{'error':'Forbidden host/origin'})
            if self.path=='/':
                raw=Path(__file__).with_name('flash.html').read_text(encoding='utf-8').replace('__CSRF__',flasher.csrf).encode()
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Frame-Options','DENY')
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
                return
            if self.path=='/api/state' and self.headers.get('X-CSRF-Token')==flasher.csrf:
                return self.send(200,flasher.state())
            return self.send(403 if self.path=='/api/state' else 404,{'error':'请求未授权或页面不存在。'})

        def do_POST(self):
            if not self.allowed() or self.headers.get('X-CSRF-Token') != flasher.csrf:
                return self.send(403,{'error':'Forbidden'})
            if self.path!='/api/start':
                return self.send(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1024:
                    raise ValueError('请求过大或为空。')
                data=json.loads(self.rfile.read(length))
                self.send(202,flasher.start(data))
            except (ValueError,TypeError) as error:
                self.send(400,{'error':str(error)})
            except RuntimeError as error:
                self.send(409,{'error':str(error)})
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--port',type=int,default=PORT,help='维护测试用；普通入口固定为8770')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Invalid port')
    url=f'http://127.0.0.1:{args.port}/'
    try:
        lease=ROOT/('build/flash-ui.lock' if args.port==PORT else f'build/flash-ui-{args.port}.lock')
        with ServiceLease(lease):
            server=ExclusiveLoopbackServer(('127.0.0.1',args.port),make_handler(Flasher()))
            if not args.no_browser:webbrowser.open(url)
            try:server.serve_forever()
            finally:server.server_close()
    except ServiceAlreadyRunning:
        if not args.no_browser:webbrowser.open(url)


if __name__=='__main__':main()
