"""Local installation and control panel. Bootstrap uses only Python's standard library."""
import argparse
from collections import deque
import hmac
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import webbrowser

from service_lifecycle import ExclusiveLoopbackServer, ServiceLease, ServiceAlreadyRunning

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/device-lab'
PORT = 8769
COLLECTOR = 'http://127.0.0.1:8768'
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROFILE_COUNTS = {'status': 2, 'history': 9, 'interaction': 13}


def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8-sig')) if Path(path).is_file() else default


def request_collector(path, data=None, timeout=5):
    private = read_json(WORK / 'companion-private.json', {})
    if not private.get('token'):
        raise ValueError('电脑采集服务尚未安装，请先完成环境准备和设备配对。')
    headers = {'Authorization': 'Bearer ' + private['token'], 'Content-Type': 'application/json'}
    request = urllib.request.Request(COLLECTOR + path, headers=headers,
        data=json.dumps(data).encode() if data is not None else None)
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(json.loads(error.read()).get('error', '采集服务请求失败。')) from None


def collector_start():
    try:
        connection = request_collector('/connection', timeout=2)
        return dict(running=True, reused=True, connection=connection)
    except (OSError, ValueError):
        pass
    from owned_processes import launch
    child, _ = launch([sys.executable, '-X', 'utf8', str(ROOT / 'tools/run_background.py')], ROOT)
    for _ in range(40):
        try:
            return dict(running=True, reused=False, connection=request_collector('/connection', timeout=1))
        except (OSError, ValueError):
            if child.poll() is not None:
                raise ValueError('采集服务未能启动，请检查串口占用、配对或 8768 端口。') from None
            time.sleep(.25)
    raise ValueError('采集服务启动尚未完成，请查看诊断并重新检查状态。')


def collector_stop():
    try:
        request_collector('/companion/shutdown', {}, timeout=3)
    except (urllib.error.URLError, ConnectionError):
        return dict(running=False)
    for _ in range(40):
        try:
            request_collector('/connection', timeout=.5)
        except (urllib.error.URLError, ConnectionError):
            return dict(running=False)
        time.sleep(.1)
    raise ValueError('采集服务正在退出，请稍后检查。')


def pair_device(data):
    from device_transport import WifiLink, save_connection
    from private_storage import write_json
    config = read_json(WORK / 'device-private.json', {})
    candidate = dict(config)
    if data.get('token'):
        candidate['mcp_token'] = data['token'].strip()
        # A new token can explicitly pair a different device.
        candidate.pop('device_id', None)
        candidate.pop('state', None)
    if data.get('admin_password'):
        candidate['ap_password'] = data['admin_password']
    if data.get('admin_user'):
        candidate['admin_user'] = data['admin_user'].strip()
    try:
        link = WifiLink(data.get('host', '').strip(), candidate, timeout=4)
        status = link.exchange({'cmd': 'status'})
    except (ValueError, RuntimeError, OSError):
        raise ValueError('配对失败，请检查设备 IP、MCP 开关、令牌和同一局域网。原配置未修改。') from None
    candidate.update(device_id=status['device_id'], state=status)
    # Stop the authenticated project collector before changing its connection.
    if read_json(WORK / 'companion-private.json', {}):
        collector_stop()
    write_json(WORK / 'device-private.json', candidate)
    save_connection(WORK / 'connection-private.json', 'wifi', link.host)
    collector_start()
    return dict(paired=True, device_id=status['device_id'], device_host=link.host)


def worker(action, data):
    """Runs in the installed environment; credentials arrive on stdin, never argv."""
    if action == 'pair':
        return pair_device(data)
    if action == 'usb-pair-wifi':
        from device_lab import SerialLink
        port = data.get('port','COM3').strip()
        if not port.upper().startswith('COM') or not port[3:].isdigit():
            raise ValueError('请输入实际串口，例如 COM3。')
        saved = read_json(WORK / 'connection-private.json', {})
        if saved.get('transport') == 'usb':
            collector_stop()
        link = SerialLink(port)
        try:
            state = link.exchange({'cmd':'status'})
            setup = link.exchange({'cmd':'setup'})
        finally:
            link.close()
        if not state.get('wifi_connected') or not state.get('ip'):
            raise ValueError('设备还未联网，请先给设备配网，再点击一键配对。')
        return pair_device(dict(host=state['ip'],token=setup.get('mcp_token',''),
            admin_user=setup.get('admin_user','admin'),admin_password=setup.get('ap_password','')))
    if action == 'usb':
        from device_transport import save_connection
        port = data.get('port', '').strip()
        if not port.upper().startswith('COM') or not port[3:].isdigit():
            raise ValueError('请输入实际串口，例如 COM3。')
        collector_stop() if read_json(WORK / 'companion-private.json', {}) else None
        save_connection(WORK / 'connection-private.json', 'usb', port=port)
        return collector_start()
    if action == 'discover':
        # The collector owns IP recovery; no second process races saved credentials.
        collector_start()
        return request_collector('/companion/tool', {'name': 'discover_paired_device',
            'arguments': {'update_connection': True}}, timeout=12)
    if action == 'collector-start':
        return collector_start()
    if action == 'collector-check':
        collector_start()
        installation = request_collector('/companion/tool', {'name': 'get_installation_status', 'arguments': {}})
        try:
            device = request_collector('/companion/tool', {'name': 'doll_get_status', 'arguments': {}})
            return dict(installation=installation, device=device, device_error=None)
        except (OSError, ValueError):
            return dict(installation=installation, device=None,
                        device_error='设备当前不可达，请检查供电、局域网及 MCP 开关。电脑历史仍可查询。')
    if action == 'collector-stop':
        import secure_mcp
        secure_mcp.stop()
        return collector_stop()
    if action == 'secure-save':
        import secure_mcp
        return secure_mcp.configure(secure_mcp.DEFAULT, data.get('tunnel_id', ''),
            data.get('api_key', ''), data.get('profile', 'interaction'))
    if action in ('secure-start', 'secure-stop', 'secure-status', 'secure-reset'):
        import secure_mcp
        if action == 'secure-start':
            collector_start()
        fn = {'secure-start': secure_mcp.start, 'secure-stop': secure_mcp.stop,
              'secure-status': lambda: secure_mcp.status(verify=True), 'secure-reset': secure_mcp.reset_address}[action]
        return fn()
    if action == 'tunnel-install':
        from install_tunnel_client import install
        _, version = install()
        return dict(installed=True, version=version)
    if action == 'client-config':
        import install_companion_mcp
        sys.argv = [sys.argv[0]]
        install_companion_mcp.main()
        return read_json(WORK / 'mcp-client-config.json')
    if action == 'verify-chat':
        from verify_chat_calls import correlate
        return correlate(ROOT / 'build/device-lab/secure-mcp',
            data.get('installation_call_id', '').strip(), data.get('device_call_id', '').strip())
    if action == 'startup':
        from configure_startup import configure
        return configure(data.get('action', 'status'))
    if action == 'ota':
        import base64
        from ota_device import OtaClient, validate_image
        if data.get('confirmed') is not True:
            raise ValueError('请先确认要刷写所选固件。')
        connection = read_json(WORK / 'connection-private.json', {})
        config = read_json(WORK / 'device-private.json', {})
        if connection.get('transport') != 'wifi':
            raise ValueError('无线升级需要先完成 Wi-Fi 配对，或打开设备设置页升级。')
        if data.get('bundled'):
            image = (ROOT / 'firmware/prebuilt/firmware.bin').read_bytes()
            manifest = read_json(ROOT / 'firmware/prebuilt/FLASH_MANIFEST.json')
        else:
            image = base64.b64decode(data.get('image_base64', ''), validate=True)
            manifest = data.get('manifest', {})
        validate_image(image, manifest)
        return OtaClient(connection['device_host'], config).upload(image, manifest)
    raise ValueError('未知操作。')


class Panel:
    def __init__(self):
        self.csrf = secrets.token_hex(24)
        self.lock = threading.Lock()
        self.job = dict(state='idle', action='', message='欢迎使用 AI Doll。', result=None)
        self.messages = deque(maxlen=80)
        self.secure = {}
        self.ready = self.check_environment()

    @property
    def python(self):
        bundled = ROOT / 'python/python.exe'
        if os.name == 'nt' and bundled.is_file():
            return bundled
        return ROOT / ('.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python')

    def check_environment(self):
        if not self.python.is_file():
            return False
        result = subprocess.run([str(self.python), '-I', '-c',
            'import mcp,httpx,serial; from importlib.metadata import version; '
            'assert version("mcp")=="1.30.0" and version("httpx")=="0.28.1" and version("pyserial")=="3.5"'],
            capture_output=True, timeout=15, creationflags=FLAGS)
        return result.returncode == 0

    def note(self, message):
        with self.lock:
            self.job['message'] = message
            self.messages.append(dict(at=time.time(), message=message))

    def run_worker(self, action, data=None):
        command = [str(self.python), '-X', 'utf8', str(Path(__file__)), '--worker', action]
        result = subprocess.run(command, input=json.dumps(data or {}), text=True, encoding='utf-8',
            capture_output=True, timeout=300, creationflags=FLAGS, cwd=ROOT)
        try:
            output = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise ValueError('操作未完成。请检查环境准备、设备连接或端口占用后重试。') from None
        if result.returncode or output.get('error'):
            raise ValueError(output.get('error', '操作失败。'))
        return output

    def install(self):
        if self.python == ROOT / 'python/python.exe':
            self.note('正在检查软件包内置运行环境…')
            self.ready = self.check_environment()
            if not self.ready:
                raise ValueError('内置依赖不完整，请重新解压完整软件包并保留 python 文件夹。')
            self.run_worker('client-config')
            return dict(installed=True, bundled=True)
        if not self.python.is_file():
            self.note('正在创建项目运行环境…')
            base = Path(sys.executable).with_name('python.exe') if os.name == 'nt' else Path(sys.executable)
            result = subprocess.run([str(base), '-I', '-m', 'venv', str(ROOT / '.venv')],
                capture_output=True, timeout=90, creationflags=FLAGS)
            if result.returncode:
                raise ValueError('无法创建运行环境，请检查项目目录是否可写及 Python 安装。')
        self.note('正在安装依赖，首次使用需要联网…')
        result = subprocess.run([str(self.python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check',
            '-r', str(ROOT / 'requirements-companion.txt')], capture_output=True, timeout=300, creationflags=FLAGS)
        self.ready = self.check_environment()
        if result.returncode or not self.ready:
            raise ValueError('依赖安装失败。请检查电脑联网或已配置的代理，再点击重试。')
        self.run_worker('client-config')
        return dict(installed=True)

    def perform(self, action, data):
        if action == 'install':
            return self.install()
        if not self.ready:
            raise ValueError('请先在“安装引导”中准备运行环境。')
        if action == 'daily-start':
            self.note('正在启动电脑采集服务…')
            local = self.run_worker('collector-start')
            config = read_json(WORK / 'secure-mcp/secure-private.json', {})
            if config.get('runtime_api_key'):
                self.note('正在连接 ChatGPT 隧道…')
                self.secure = self.run_worker('secure-start')
            self.run_worker('client-config')
            return dict(collector=local, secure=self.secure)
        result = self.run_worker(action, data)
        if action.startswith('secure-'):
            self.secure = result
        if action == 'collector-stop':
            self.secure = {}
        return result

    def submit(self, action, data):
        allowed = {'install', 'pair', 'usb', 'usb-pair-wifi', 'discover', 'collector-start', 'collector-stop',
            'secure-save', 'secure-start', 'secure-stop', 'secure-status', 'secure-reset', 'collector-check',
            'client-config', 'verify-chat', 'startup', 'tunnel-install', 'daily-start', 'ota'}
        if action not in allowed:
            raise ValueError('未知操作。')
        with self.lock:
            if self.job['state'] == 'running':
                raise ValueError('正在完成上一项操作，请稍候。')
            self.job = dict(state='running', action=action, message='正在处理…', result=None)
        def execute():
            try:
                result = self.perform(action, data)
                with self.lock:
                    self.job.update(state='done', message='操作完成。', result=result)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                message = str(error) if isinstance(error, ValueError) else '操作超时或服务未响应，请检查连接并重试。'
                if action == 'ota' and isinstance(error, subprocess.TimeoutExpired):
                    message = '升级状态尚未确认，请先检查设备新启动版本，不要直接重复写入。'
                with self.lock:
                    self.job.update(state='error', message=message, result=None)
        threading.Thread(target=execute, daemon=True).start()
        return dict(accepted=True)

    def state(self):
        pairing = read_json(WORK / 'device-private.json', {})
        connection = read_json(WORK / 'connection-private.json', {})
        cfg = read_json(WORK / 'secure-mcp/secure-private.json', {})
        local = dict(running=False)
        try:
            current = request_collector('/connection', timeout=1)
            local.update(running=True, **current)
        except (OSError, ValueError):
            pass
        with self.lock:
            task, messages = dict(self.job), list(self.messages)
        return dict(environment_ready=self.ready, python_version=sys.version.split()[0],
            paired=bool(pairing.get('mcp_token') and pairing.get('device_id')),
            device_id=pairing.get('device_id'), connection=connection, collector=local,
            secure_config=dict(configured=bool(cfg), tunnel_id=cfg.get('tunnel_id', ''),
                profile=cfg.get('profile', 'interaction'), key_saved=bool(cfg.get('runtime_api_key'))),
            secure=self.secure, job=task, messages=messages,
            project=str(ROOT), version='2.16.1')


def make_handler(panel):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            hosts = (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
            return self.headers.get('Host') in hosts and self.headers.get('Origin', '') in ('', *('http://' + h for h in hosts))

        def send(self, status, data, mime='application/json; charset=utf-8'):
            raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return self.allowed() and hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), panel.csrf)

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {'error': 'Forbidden'})
            path = urlsplit(self.path).path
            if path in ('/', '/control-panel.js'):
                asset = ROOT / 'tools' / ('control_panel.html' if path == '/' else 'control_panel.js')
                raw = asset.read_text(encoding='utf-8').replace('__CSRF__', panel.csrf).encode()
                return self.send(200, raw, 'text/html; charset=utf-8' if path == '/' else 'application/javascript; charset=utf-8')
            if not self.authorized():
                return self.send(403, {'error': 'Forbidden'})
            if path == '/api/state':
                return self.send(200, panel.state())
            if path == '/api/client-config':
                return self.send(200, read_json(WORK / 'mcp-client-config.json', {}))
            if path == '/api/diagnostics':
                # Structured state only: no raw exception log, history or credentials.
                return self.send(200, panel.state())
            return self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.authorized():
                return self.send(403, {'error': 'Forbidden'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2 * 1024 * 1024:
                    return self.send(413, {'error': 'Request too large'})
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or not isinstance(data.get('data', {}), dict):
                    raise ValueError('请求格式错误。')
                if self.path != '/api/action':
                    return self.send(404, {'error': 'Not found'})
                return self.send(202, panel.submit(data.get('action'), data.get('data', {})))
            except (ValueError, TypeError) as error:
                return self.send(400, {'error': str(error)})
    return Handler


def main():
    global PORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--autostart', action='store_true')
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    PORT = args.port
    if args.worker:
        try:
            result = worker(args.worker, json.load(sys.stdin))
            print(json.dumps(result, ensure_ascii=False))
        except Exception as error:
            # Device and tunnel adapters already provide safe user-facing errors.
            message = str(error) if isinstance(error, (ValueError, RuntimeError)) else '操作失败，请检查连接和运行环境。'
            print(json.dumps({'error': message}, ensure_ascii=False))
            raise SystemExit(1)
        return
    url = f'http://127.0.0.1:{PORT}/'
    try:
        with ServiceLease(WORK / 'control-panel.lock'):
            panel = Panel()
            server = ExclusiveLoopbackServer(('127.0.0.1', PORT), make_handler(panel))
            if panel.ready and panel.python == ROOT/'python/python.exe' and not (WORK/'mcp-client-config.json').is_file():
                panel.install()
            if args.autostart and panel.ready and read_json(WORK / 'connection-private.json'):
                panel.submit('daily-start', {})
            if not args.no_browser:
                webbrowser.open(url)
            try:
                server.serve_forever()
            finally:
                server.server_close()
    except ServiceAlreadyRunning:
        if args.autostart:
            with OPENER.open(url, timeout=3) as response:
                page = response.read(150000).decode('utf-8')
            token = re.search(r"window.PANEL_CSRF='([0-9a-f]{48})'", page)
            if token:
                request = urllib.request.Request(url + 'api/action',
                    data=json.dumps({'action': 'daily-start', 'data': {}}).encode(),
                    headers={'Content-Type': 'application/json', 'X-CSRF-Token': token[1]})
                try:
                    OPENER.open(request, timeout=3).close()
                except urllib.error.HTTPError:
                    pass  # The existing GUI displays the active installation/operation.
        if not args.no_browser:
            webbrowser.open(url)
    except OSError:
        if not args.no_browser and os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                '管理中心未能启动，请检查 8769 端口是否被其他程序占用，以及项目目录是否可写。', 'AI Doll', 0x10)
        else:
            raise


if __name__ == '__main__':
    main()
