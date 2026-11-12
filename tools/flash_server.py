"""Local one-button flasher. All device writes use the verified CLI engine."""
import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import tempfile
import threading
from types import SimpleNamespace
import webbrowser

from flash_esp32 import ROOT, DEFAULT_BAUD, FlashJob, flash, select_port, validate_name
from flash_sources import (MAX_DOWNLOAD, describe, prepare_zip, prepare_upload,
                           latest_release, download_release)
from service_lifecycle import ExclusiveLoopbackServer, ServiceLease, ServiceAlreadyRunning

PORT = 8770


class Flasher:
    def __init__(self):
        self.csrf = secrets.token_hex(24)
        self.lock = threading.Lock()
        self.job = None
        self.running = False
        self.preparing = False
        self.images = ROOT / 'firmware/prebuilt'
        self.source = dict(kind='bundled', label='随包固件', source_id=None)
        self.latest = None
        self.cache = ROOT / 'build/flash-sources'

    @contextmanager
    def preparation(self):
        with self.lock:
            if self.running or self.preparing:
                raise RuntimeError('正在烧录或准备固件，请等待完成。')
            self.preparing = True
        try:
            yield
        finally:
            with self.lock:
                self.preparing = False

    def choose(self, kind, loader, label, **extra):
        with self.preparation():
            images = loader()
            source = describe(images, kind, label, **extra)
            with self.lock:
                self.images, self.source = images, source
        return source

    def check_latest(self):
        with self.preparation():
            latest = latest_release()
            with self.lock:
                self.latest = latest
        return latest

    def choose_release(self):
        with self.lock:
            release = self.latest
        if not release:
            raise ValueError('请先查询 GitHub 最新版本。')
        return self.choose('github', lambda: download_release(release, self.cache),
                           'GitHub · ' + release['tag'], release_url=release['release_url'],
                           asset_name=release['asset_name'])

    def state(self):
        from serial.tools.list_ports import comports
        ports = list(comports())
        try:
            selected = select_port(ports)
        except ValueError:
            selected = ''
        with self.lock:
            images, source = self.images, self.source.copy()
            job, running, preparing, latest = self.job, self.running, self.preparing, self.latest
        try:
            source.update(describe(images, source['kind'], source['label']))
            firmware, image_error = source['firmware'], None
        except (ValueError, OSError, KeyError) as error:
            firmware, image_error = None, str(error)
        report, log = None, ''
        if job:
            report = job.snapshot()
            log = job.logfile.read_text(encoding='utf-8', errors='replace')[-16000:]
        return dict(app='ai-doll-flasher', ports=[dict(port=p.device, description=p.description) for p in ports],
                    selected_port=selected, firmware=firmware, image_error=image_error,
                    running=running, preparing=preparing, source=source, latest=latest,
                    report=report, log=log,
                    result_folder=str(job.folder) if job else None)

    def start(self, data):
        if not isinstance(data,dict) or set(data)-{'port','factory','factory_confirmed','name','source_id'}:
            raise ValueError('请求格式不正确。')
        if not isinstance(data.get('port',''),str) or type(data.get('factory',False)) is not bool:
            raise ValueError('串口或烧录方式不正确。')
        if data.get('factory') and data.get('factory_confirmed') is not True:
            raise ValueError('恢复出厂需要勾选清除设备设置确认。')
        name = validate_name(data.get('name'))
        with self.lock:
            if self.running or self.preparing:
                raise RuntimeError('正在烧录或准备固件，请等待完成。')
            if data.get('source_id') is not None and data['source_id'] != describe(
                    self.images, self.source['kind'], self.source['label'])['source_id']:
                raise ValueError('固件选择已变化，请刷新页面后确认。')
            self.job = FlashJob()
            self.job.update(firmware_source=self.source.copy())
            self.running = True
            job = self.job
            images = self.images
        args = SimpleNamespace(port=data.get('port') or None, baud=DEFAULT_BAUD, name=name,
                               images=images, factory=data.get('factory',False), boot_timeout=180)
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
            if self.path not in ('/api/start', '/api/firmware/bundled', '/api/firmware/local',
                                 '/api/releases/latest', '/api/firmware/release'):
                return self.send(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                archive = self.path == '/api/firmware/local' and self.headers.get('Content-Type') == 'application/zip'
                limit = MAX_DOWNLOAD if archive else 8 * 1024 * 1024 if self.path == '/api/firmware/local' else 1024
                if not 0 < length <= limit:
                    raise ValueError('请求过大或为空。')
                if archive:
                    def load_archive():
                        flasher.cache.mkdir(parents=True, exist_ok=True)
                        with tempfile.TemporaryFile(dir=flasher.cache) as upload:
                            remaining = length
                            while remaining:
                                block = self.rfile.read(min(remaining, 128 * 1024))
                                if not block:
                                    raise ValueError('固件上传中断，请重新选择文件。')
                                upload.write(block)
                                remaining -= len(block)
                            upload.seek(0)
                            return prepare_zip(upload, flasher.cache)
                    return self.send(200, flasher.choose('local', load_archive, '本地固件 ZIP'))
                data=json.loads(self.rfile.read(length))
                if self.path == '/api/start':
                    return self.send(202,flasher.start(data))
                if self.path == '/api/firmware/local':
                    result = flasher.choose('local', lambda: prepare_upload(data, flasher.cache), '本地固件文件')
                elif data != {}:
                    raise ValueError('请求格式不正确。')
                elif self.path == '/api/firmware/bundled':
                    result = flasher.choose('bundled', lambda: ROOT/'firmware/prebuilt', '随包固件')
                elif self.path == '/api/releases/latest':
                    result = flasher.check_latest()
                else:
                    result = flasher.choose_release()
                self.send(200,result)
            except (ValueError,TypeError) as error:
                self.send(400,{'error':str(error)})
            except RuntimeError as error:
                self.send(409,{'error':str(error)})
            except OSError as error:
                message = '无法保存烧录记录，请检查项目目录是否可写：' if self.path == '/api/start' else '准备固件失败，请检查网络及项目目录：'
                self.send(500,{'error':message+str(error)})
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
