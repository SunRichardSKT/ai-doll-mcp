"""Owned LAN MCP service and one-time phone connection export; no shell launcher."""
import argparse
import asyncio
import ipaddress
import json
import logging
from pathlib import Path
import socket
import sys
import time

from owned_processes import alive, launch, terminate
from private_storage import write_json
from service_lifecycle import ServiceLease

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build/device-lab/operit'
CHILDREN = {}


def read(path, default=None):
    if not path.is_file():
        return default
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Operit 配置格式不正确，原文件保留。')
    return value


def lan_addresses():
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        return []
    blocks = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    return sorted(value for value in addresses if any(ipaddress.ip_address(value) in block for block in blocks))


def config():
    value = read(WORK / 'settings-private.json')
    if value and (value.get('schema') != 1 or value.get('mode') not in ('device', 'simulation') or
                  type(value.get('port')) is not int or not 1024 <= value['port'] <= 65535 or
                  value.get('host') not in lan_addresses()):
        raise ValueError('电脑网络已变化或配置不可用，请在 Operit 页面重新选择当前局域网地址。')
    return value


def save(mode='device', host=None):
    if mode not in ('device', 'simulation'):
        raise ValueError('请选择真实设备或模拟演示。')
    addresses = lan_addresses()
    if not host and len(addresses) == 1:
        host = addresses[0]
    if not host or host not in addresses:
        raise ValueError('请选择手机和电脑所在的局域网地址；只有一个可用地址时会自动选择。')
    with ServiceLease(WORK / 'control.lock'):
        current = read(WORK / 'settings-private.json')
        process = read(WORK / 'process-private.json')
        if alive(process) and current and (current['host'] != host or current['mode'] != mode):
            terminate(process)
            if alive(process):
                raise ValueError('旧 Operit 服务尚未停止，原配置保留。')
            if process['pid'] in CHILDREN:
                CHILDREN.pop(process['pid']).wait(timeout=5)
        write_json(WORK / 'settings-private.json', dict(schema=1, mode=mode, host=host,
                   port=current['port'] if current else 8775, enabled=True))
    return dict(saved=True, mode=mode, host=host)


def location(cfg):
    if WORK != ROOT / 'build/device-lab/operit':
        return WORK / cfg['mode'] / 'mcp'
    return (ROOT / 'build/operit-demo/mcp') if cfg['mode'] == 'simulation' else (ROOT / 'build/device-lab/operit-mcp')


def address(cfg):
    from remote_mcp import CapabilityStore
    return CapabilityStore(location(cfg)).local_url(cfg['host'], cfg['port'])


async def protocol_check(url):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('mcp.client.streamable_http').setLevel(logging.WARNING)
    async with httpx.AsyncClient(trust_env=False, timeout=4) as http:
        async with streamable_http_client(url, http_client=http) as (reader, writer, _):
            async with ClientSession(reader, writer) as sdk:
                await sdk.initialize()
                names = {tool.name for tool in (await sdk.list_tools()).tools}
                required = {'get_installation_status', 'get_device_overview', 'get_chat_context',
                            'start_interaction', 'acknowledge_chat_context'}
                if not required.issubset(names) or len(names) != 19:
                    raise ValueError('Operit MCP 工具发现不完整。')
                return dict(protocol_connected=True, tool_count=len(names))


def status(verify=False):
    try:
        value = read(WORK / 'settings-private.json')
        process = read(WORK / 'process-private.json')
    except (ValueError, OSError):
        return dict(configured=True, running=False, protocol_connected=False, addresses=lan_addresses(),
                    error='Operit 配置无法读取，原文件保留。请检查目录权限或从备份恢复。',
                    background_chat_verified=False)
    result = dict(configured=bool(value), running=alive(process), protocol_connected=False,
                  mode=value.get('mode') if value else None,
                  host=value.get('host') if value else None, addresses=lan_addresses(),
                  port=value.get('port') if value else 8775,
                  background_chat_verified=False)
    result['host_available'] = result['host'] in result['addresses']
    if value and result['host'] not in result['addresses']:
        result['error'] = '电脑 IP 已变化，请选择当前地址并保存启动，再在手机 AI Doll 设置修改电脑 IP。无需重新导入或绑定聊天。'
        return result
    if verify and value and result['running']:
        try:
            result.update(asyncio.run(asyncio.wait_for(protocol_check(address(value)), 6)))
        except Exception:
            result['error'] = '进程存在，但 MCP 尚未通过连接检查。请检查网络和端口。'
    return result


def start():
    cfg = config()
    if not cfg:
        raise ValueError('请在 Operit 页面选择运行模式并保存。')
    with ServiceLease(WORK / 'control.lock'):
        process = read(WORK / 'process-private.json')
        reused = alive(process)
        if not reused:
            # Check the exact interface; never terminate an unrelated port owner.
            with socket.socket() as probe:
                try:
                    probe.bind((cfg['host'], cfg['port']))
                except OSError:
                    raise ValueError('8775 端口正在使用，未停止其他程序。请关闭旧 Operit 启动窗口后重试。') from None
            child, process = launch([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                                 'serve', '--data-dir', str(WORK)], ROOT)
            CHILDREN[process['pid']] = child
            write_json(WORK / 'process-private.json', process)
        for _ in range(25):
            if not alive(process):
                break
            try:
                check = asyncio.run(asyncio.wait_for(protocol_check(address(cfg)), 2))
                return dict(running=True, reused=reused, mode=cfg['mode'], **check)
            except Exception:
                time.sleep(.15)
    raise ValueError('服务未通过启动检查。配置和历史保留，请检查运行环境或原采集服务。')


def stop():
    with ServiceLease(WORK / 'control.lock'):
        process = read(WORK / 'process-private.json')
        if alive(process):
            terminate(process)
        if alive(process):
            raise ValueError('本项目 Operit 进程尚未停止，请稍后检查。')
        if process and process.get('pid') in CHILDREN:
            CHILDREN.pop(process['pid']).wait(timeout=5)
    return dict(stopped=True, history_preserved=True)


def export_connection():
    cfg = config()
    if not cfg or not status(verify=True)['protocol_connected']:
        raise ValueError('请先启动并检查 Operit 服务，再导出手机连接。')
    return dict(schema=1, kind='ai-doll-operit-connection', mcp_url=address(cfg),
                mode=cfg['mode'], label='AI Doll · '+('模拟演示' if cfg['mode'] == 'simulation' else '真实设备'),
                version='2.21.0')


def serve():
    import uvicorn
    from remote_mcp import create_private_remote
    cfg = config()
    if not cfg:
        raise ValueError('Missing saved configuration')
    logging.disable(logging.CRITICAL)
    with ServiceLease(WORK / 'service.lock'):
        demo = None
        if cfg['mode'] == 'simulation':
            from operit_demo import DemoBackend
            import companion_mcp
            demo = DemoBackend(location(cfg).parent)
            companion_mcp.call = demo.call
        try:
            _, app, _ = create_private_remote(location(cfg), port=cfg['port'], listen_host=cfg['host'])
            uvicorn.run(app, host=cfg['host'], port=cfg['port'], access_log=False, log_level='critical')
        finally:
            if demo:
                demo.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('serve', 'start', 'stop', 'status'))
    parser.add_argument('--data-dir', type=Path, default=WORK, help=argparse.SUPPRESS)
    args = parser.parse_args()
    WORK = args.data_dir.resolve()
    action = args.action
    if action == 'serve':
        serve()
    else:
        print(json.dumps({'start': start, 'stop': stop, 'status': lambda: status(verify=True)}[action](), ensure_ascii=False))
