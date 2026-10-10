"""Dedicated Secure MCP Tunnel lifecycle for the existing Wi-Fi collector."""
import argparse
import asyncio
import datetime as dt
import getpass
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import uuid

from deploy_mcp import PROFILES, ROOT, probe_url, read_json
from install_tunnel_client import install as install_client
from owned_processes import alive, launch, terminate
from private_storage import private_directory, write_json, write_private
from remote_mcp import CapabilityStore
from service_lifecycle import ServiceLease

DEFAULT = ROOT / 'build/device-lab/secure-mcp'
DEFAULT_PORT = 8774
TUNNEL_ID = re.compile(r'tunnel_[0-9a-f]{32}')


class SecureError(RuntimeError):
    """Messages are safe for the local GUI and console; raw diagnostics stay local."""


def configuration(folder, required=False):
    value = read_json(Path(folder) / 'secure-private.json', {})
    if not value:
        if required:
            raise SecureError('请先打开配置窗口，填写隧道 ID 和运行 API 密钥。')
        return {}
    if (value.get('schema') != 1 or not TUNNEL_ID.fullmatch(value.get('tunnel_id', ''))
            or value.get('profile') not in PROFILES
            or not re.fullmatch(r'ai-doll-[0-9a-f]{16}', value.get('alias', ''))
            or type(value.get('port')) is not int or not 1024 <= value['port'] <= 65535):
        raise SecureError('本机隧道配置无效，请重新保存配置。')
    return value


def configure(folder, tunnel_id, api_key='', profile='interaction', port=DEFAULT_PORT):
    folder = private_directory(Path(folder).resolve())
    tunnel_id, api_key = tunnel_id.strip(), api_key.strip()
    if not TUNNEL_ID.fullmatch(tunnel_id):
        raise SecureError('隧道 ID 应为 tunnel_ 开头，后接 32 位编号。')
    if profile not in PROFILES or type(port) is not int or not 1024 <= port <= 65535:
        raise SecureError('工具范围或本地端口无效。')
    if api_key and (not re.fullmatch(r'sk-[A-Za-z0-9_-]{12,1000}', api_key)
                    or api_key.startswith('sk-admin-')):
        raise SecureError('请填写 Platform 的运行 API 密钥，不使用管理密钥。')
    with ServiceLease(folder / 'operation.lock'):
        previous = configuration(folder)
        value = dict(schema=1, alias=previous.get('alias', 'ai-doll-' + uuid.uuid4().hex[:16]),
                     tunnel_id=tunnel_id, profile=profile, port=port,
                     runtime_api_key=api_key or previous.get('runtime_api_key', ''))
        # A changed target/profile/key must be applied to a fresh native runtime.
        # Stop using the OLD configuration first, so its ownership remains checkable.
        if previous and value != previous:
            _stop(folder, previous)
        write_json(folder / 'secure-private.json', value)
        if value['runtime_api_key']:
            write_private(folder / 'runtime-api.key', value['runtime_api_key'] + '\n')
        CapabilityStore(folder / 'gateway')
    return dict(configured=True, key_saved=bool(value['runtime_api_key']),
                tunnel_id=tunnel_id, profile=profile)


def native(folder, args, timeout=55):
    """Use the official managed runtime in an isolated project state directory."""
    folder = Path(folder).resolve()
    executable, version = install_client()
    state = private_directory(folder / 'native-state')
    env = dict(os.environ, TUNNEL_CLIENT_STATE_DIR=str(state),
               TUNNEL_CLIENT_PROFILE_DIR=str(private_directory(folder / 'profiles')))
    # Never accidentally inherit admin or unrelated runtime credentials.
    for name in ('CONTROL_PLANE_API_KEY', 'OPENAI_ADMIN_KEY', 'OPENAI_API_KEY'):
        env.pop(name, None)
    # Go does not automatically use Windows Internet Settings. Honor the proxy
    # already chosen on this PC for outbound OpenAI traffic, without changing
    # system settings or proxying loopback MCP / the LAN device.
    proxies = urllib.request.getproxies()
    proxy = env.get('CONTROL_PLANE_HTTP_PROXY') or proxies.get('https') or proxies.get('http')
    if proxy:
        target = urlsplit(proxy)
        if target.scheme not in ('http', 'https') or not target.hostname:
            raise SecureError('当前出站代理无效；请检查电脑网络代理设置。')
        env.update(CONTROL_PLANE_HTTP_PROXY=proxy, HTTPS_PROXY=proxy)
    bypass = [item.strip() for item in env.get('NO_PROXY', env.get('no_proxy', '')).split(',') if item.strip()]
    env['NO_PROXY'] = ','.join(dict.fromkeys(bypass + ['127.0.0.1', 'localhost', '::1']))
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        result = subprocess.run([str(executable), 'runtimes', *args, '--json'],
                                cwd=ROOT, env=env, capture_output=True, timeout=timeout,
                                creationflags=flags)
    except subprocess.TimeoutExpired:
        # Native supervision may have started the daemon. Do not kill/restart it
        # on an observation timeout; the next status reads its actual identity.
        raise SecureError('客户端检查超时；请点“检查状态”，不要重复启动。') from None
    raw = result.stdout.decode('utf-8', errors='replace')
    write_json(folder / 'native-command-private.json', dict(
        operation=args[0], checked_at=time.time(), version=version, exit_code=result.returncode,
        stdout=raw, stderr=result.stderr.decode('utf-8', errors='replace')))
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError()
    except ValueError:
        raise SecureError('官方客户端未返回状态；请检查网络或本机诊断文件。') from None
    return payload


def native_inventory(folder):
    # Official *.yaml state files contain JSON in v0.0.16. Read only our isolated
    # state; no global aliases or processes are adopted or stopped.
    return read_json(Path(folder) / 'native-state/aliases.yaml', {})


def check_native_owner(folder, cfg, payload=None):
    entry = native_inventory(folder).get(cfg['alias'])
    if entry is None:
        return False
    expected = (Path(folder) / 'profiles' / (cfg['alias'] + '.yaml')).resolve()
    if (entry.get('tunnel_id') != cfg['tunnel_id']
            or Path(entry.get('config_path', '')).resolve() != expected):
        raise SecureError('隧道运行记录与本项目不匹配，未停止或接管该进程。')
    if payload is not None:
        returned_id = payload.get('tunnel_id') or payload.get('tunnel', {}).get('id')
        if payload.get('alias') != cfg['alias'] or returned_id != cfg['tunnel_id']:
            raise SecureError('官方客户端返回的隧道与本项目不匹配。')
    return True


def gateway_state(folder, cfg):
    value = read_json(Path(folder) / 'gateway-process-private.json', {})
    if not value:
        return None
    expected = str((ROOT / 'tools/remote_mcp.py').resolve())
    if (value.get('entry') != expected or value.get('folder') != str((Path(folder) / 'gateway').resolve())
            or value.get('port') != cfg['port'] or value.get('profile') != cfg['profile']):
        raise SecureError('MCP 运行记录不匹配，未接管该进程。')
    return value


def local_url(folder, cfg):
    return f"http://127.0.0.1:{cfg['port']}/" + CapabilityStore(Path(folder) / 'gateway').key() + '/mcp'


def verify_local(folder, cfg, calls=False):
    prior = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        report = asyncio.run(asyncio.wait_for(probe_url(local_url(folder, cfg), cfg['profile'], calls), 35))
    except Exception:
        raise SecureError('本地 MCP 检查失败；请检查电脑采集服务和端口。') from None
    finally:
        logging.disable(prior)
    if calls:
        audit = [json.loads(line) for line in (Path(folder) / 'gateway/calls.jsonl').read_text(encoding='utf-8').splitlines()]
        for name, data in report['status_calls'].items():
            proof = data['verification']
            if not any(item.get('call_id') == proof['call_id'] and item.get('run_id') == proof['run_id']
                       and item.get('tool') == name and item.get('completed') for item in audit):
                raise SecureError('本地工具调用编号未与服务记录匹配。')
        report['call_ids_correlated'] = True
    report.update(checked_at=time.time(), scope='secure_loopback_sdk')
    write_json(Path(folder) / ('local-calls-private.json' if calls else 'local-health-private.json'), report)
    return report


def ensure_gateway(folder, cfg):
    value = gateway_state(folder, cfg)
    if alive(value):
        verify_local(folder, cfg)
        return True
    with socket.socket() as client:
        client.settimeout(.3)
        if client.connect_ex(('127.0.0.1', cfg['port'])) == 0:
            raise SecureError(f"本地端口 {cfg['port']} 已被其他程序占用，未停止其他程序。")
    entry = str((ROOT / 'tools/remote_mcp.py').resolve())
    target = str((Path(folder) / 'gateway').resolve())
    child, value = launch([sys.executable, entry, '--port', str(cfg['port']),
                          '--folder', target, '--profile', cfg['profile']], ROOT)
    value.update(entry=entry, folder=target, port=cfg['port'], profile=cfg['profile'])
    try:
        write_json(Path(folder) / 'gateway-process-private.json', value)
        for _ in range(50):
            if child.poll() is not None:
                raise SecureError('本地 MCP 未能启动。')
            with socket.socket() as client:
                client.settimeout(.1)
                if client.connect_ex(('127.0.0.1', cfg['port'])) == 0:
                    break
            time.sleep(.2)
        verify_local(folder, cfg)
    except Exception:
        terminate(value)
        raise
    return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def local_health(url):
    target = urlsplit(url)
    if (target.scheme != 'http' or target.hostname != '127.0.0.1' or not target.port
            or target.username or target.password or target.fragment):
        raise SecureError('官方客户端健康地址不是本机回环地址。')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=3) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise SecureError('健康报告过大。')
        return json.loads(raw)


def poll_observation(health, now=None):
    """Live health read still contains historical observations; require freshness."""
    now = time.time() if now is None else now
    component = health.get('components', {}).get('control-plane', {})
    details = component.get('details', {})
    def stamp(value):
        try:
            return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError, AttributeError):
            return 0
    snapshot = stamp(health.get('snapshot_at'))
    success = stamp(details.get('last_success'))
    deadline = details.get('deadline_seconds', 0)
    deadline = deadline if type(deadline) in (int, float) and 0 <= deadline <= 300 else 0
    # JSON timestamps round nanoseconds to microseconds; allow subsecond skew.
    fresh = -1 <= now - snapshot <= 10 and -1 <= now - success <= max(90, deadline + 30)
    polling = component.get('state') in ('polling', 'idle', 'backpressured')
    poll_age = details.get('current_poll_age_seconds', 0)
    age_ok = type(poll_age) in (int, float) and 0 <= poll_age <= max(90, deadline + 10)
    return dict(connected=bool(fresh and polling and age_ok and component.get('status') == 'ok'
                               and details.get('consecutive_failures') == 0),
                state=component.get('state', 'not_observed'),
                http_status=details.get('http_status'), last_success=details.get('last_success'),
                next_retry=details.get('next_retry'))


def status(folder=DEFAULT, verify=False):
    folder = Path(folder).resolve()
    cfg = configuration(folder)
    report = dict(configured=bool(cfg), key_saved=bool(cfg.get('runtime_api_key')),
                  checked_at=time.time(), gateway_running=False, runtime_running=False,
                  local_mcp_verified=False, tunnel_connected=False, ordinary_chat_verified=False)
    if not cfg:
        return report
    report.update(tunnel_id=cfg['tunnel_id'], profile=cfg['profile'], tool_count=len(PROFILES[cfg['profile']]))
    acceptance = read_json(folder / 'chat-status-acceptance-private.json', {})
    gateway = read_json(folder / 'gateway/gateway.json', {})
    report['ordinary_chat_status_verified'] = bool(acceptance.get('status_calls_correlated')
        and acceptance.get('scope') == 'user_reported_ordinary_chat_status_calls'
        and acceptance.get('run_id') == gateway.get('run_id')
        and acceptance.get('profile') == cfg['profile'])
    report['gateway_running'] = alive(gateway_state(folder, cfg))
    if verify and report['gateway_running']:
        verify_local(folder, cfg)
        report['local_mcp_verified'] = True
    if check_native_owner(folder, cfg):
        payload = native(folder, ['status', cfg['alias']])
        check_native_owner(folder, cfg, payload)
        report.update(runtime_running=payload.get('process_running') is True,
                      native_healthy=payload.get('healthy') is True, native_ready=payload.get('ready') is True)
        url = payload.get('health_details_url')
        if url and report['runtime_running']:
            try:
                health = local_health(url)
                observation = poll_observation(health)
                report['poll'] = observation
                report['tunnel_connected'] = bool(observation['connected'] and report['gateway_running']
                                                  and report['native_healthy'] and report['native_ready'])
            except (OSError, ValueError, SecureError):
                report['health_error'] = '本机健康报告暂时不可用。'
        if report['runtime_running']:
            ui = payload.get('ui_url', '')
            parsed = urlsplit(ui)
            if parsed.scheme == 'http' and parsed.hostname == '127.0.0.1':
                report['native_ui_url'] = ui
    write_json(folder / 'status-private.json', report)
    return report


def _stop(folder, cfg):
    if check_native_owner(folder, cfg):
        payload = native(folder, ['stop', cfg['alias']])
        check_native_owner(folder, cfg, payload)
        if payload.get('process_running') is True:
            raise SecureError('隧道客户端尚未停止，请再次检查状态。')
    value = gateway_state(folder, cfg)
    terminate(value)
    write_json(Path(folder) / 'gateway-process-private.json', {})


def stop(folder=DEFAULT):
    folder = private_directory(Path(folder).resolve())
    with ServiceLease(folder / 'operation.lock'):
        cfg = configuration(folder)
        if cfg:
            _stop(folder, cfg)
    return status(folder)


def start(folder=DEFAULT, local_only=False):
    folder = private_directory(Path(folder).resolve())
    with ServiceLease(folder / 'operation.lock'):
        cfg = configuration(folder, required=True)
        if not local_only and not cfg.get('runtime_api_key'):
            raise SecureError('请先在配置窗口填写运行 API 密钥。')
        # Verify the existing authenticated collector before declaring it ready.
        import companion_mcp
        try:
            collector = companion_mcp.get_installation_status()
            if collector.get('database_open') is not True:
                raise ValueError()
        except Exception:
            raise SecureError('请先运行 Install_Secure_MCP.cmd，启动并配对电脑采集服务。') from None
        reused = ensure_gateway(folder, cfg)
        verify_local(folder, cfg, calls=True)
        if not local_only:
            existing = check_native_owner(folder, cfg)
            current = native(folder, ['status', cfg['alias']]) if existing else {}
            if existing:
                check_native_owner(folder, cfg, current)
            if current.get('process_running') is not True:
                native(folder, ['connect', '--alias', cfg['alias'], '--tunnel-id', cfg['tunnel_id'],
                               '--profile', cfg['alias'], '--profile-dir', str(folder / 'profiles'),
                               '--mcp-server-url', local_url(folder, cfg),
                               '--runtime-api-key', 'file:' + str(folder / 'runtime-api.key')], timeout=90)
    report = status(folder, verify=True)
    report.update(gateway_reused=reused, local_only=local_only)
    return report


def reset_address(folder=DEFAULT):
    folder = private_directory(Path(folder).resolve())
    with ServiceLease(folder / 'operation.lock'):
        cfg = configuration(folder, required=True)
        # Invalidate the old address immediately, even if the native stop fails.
        CapabilityStore(folder / 'gateway').reset()
        _stop(folder, cfg)
    return start(folder, local_only=not bool(cfg.get('runtime_api_key')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'start', 'local-test', 'status', 'stop', 'reset-address'))
    parser.add_argument('--folder', type=Path, default=DEFAULT)
    parser.add_argument('--tunnel-id')
    parser.add_argument('--profile', choices=PROFILES, default='interaction')
    args = parser.parse_args()
    try:
        if args.action == 'configure':
            result = configure(args.folder, args.tunnel_id or input('Tunnel ID: '),
                               getpass.getpass('Runtime API key (blank keeps saved key): '), args.profile)
        elif args.action == 'start': result = start(args.folder)
        elif args.action == 'local-test': result = start(args.folder, local_only=True)
        elif args.action == 'status': result = status(args.folder, verify=True)
        elif args.action == 'stop': result = stop(args.folder)
        else: result = reset_address(args.folder)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except SecureError as error:
        print(json.dumps(dict(ok=False, error=str(error)), ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
