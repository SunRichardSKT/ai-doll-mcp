"""Verify actual local MCP calls; never infer client installation or idle wake-up."""
import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

import companion_mcp as adapter
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import httpx

ROOT = Path(__file__).resolve().parents[1]


async def inspect(client, transport):
    initialized = await client.initialize()
    listing = await client.list_tools()
    names = {tool.name for tool in listing.tools}
    required = {'get_installation_status', 'doll_get_status'}
    if not required <= names:
        raise RuntimeError('Required status tools were not discovered')
    result = {}
    for name in ('get_installation_status', 'doll_get_status'):
        response = await client.call_tool(name, {'client_kind': 'stdio'} if name == 'get_installation_status' and transport == 'stdio' else {})
        if response.isError:
            raise RuntimeError('Status tool failed: ' + name)
        result[name] = response.structuredContent or json.loads(response.content[0].text)
    installation, device = result['get_installation_status'], result['doll_get_status']
    passed = not installation.get('collector_error') and not installation.get('device_error')
    passed = bool(passed and device.get('device_id') and device.get('firmware'))
    return {
        'passed': passed, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope': 'local_sdk_status_calls', 'mcp_transport': transport,
        'negotiated_protocol': initialized.protocolVersion, 'tool_count': len(names),
        'device_id': device.get('device_id'), 'firmware': device.get('firmware'),
        'bridge': installation.get('bridge'),
        'device_transport': installation.get('runtime', {}).get('transport'),
        'wifi_connected': device.get('wifi_connected'), 'sensor_mode': device.get('sensor_mode'),
        'physical_outputs_enabled': device.get('physical_outputs_enabled'),
        'device_available': not bool(installation.get('device_error')),
        'collector_healthy': not bool(installation.get('collector_error')),
        'sdk_verification_calls': [dict(value['verification'], tool=name, origin='deployment_sdk')
                                   for name, value in result.items() if 'verification' in value],
        'target_ai_chat_verified': False, 'idle_wake_verified': False,
    }


async def verify(transport, url):
    if transport == 'stdio':
        parameters = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'tools/companion_mcp.py')])
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=dt.timedelta(seconds=60)) as client:
                return await inspect(client, transport)
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password:
        raise ValueError('This verifier accepts only loopback HTTP; remote verification is a separate deployment step')
    async with httpx.AsyncClient(trust_env=False, timeout=30) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, _):
            async with ClientSession(read, write, read_timeout_seconds=dt.timedelta(seconds=60)) as client:
                return await inspect(client, transport)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=('stdio', 'http'), default='stdio')
    parser.add_argument('--url', default='http://127.0.0.1:8771/mcp')
    parser.add_argument('--recover-device', action='store_true', help='Recover an already-paired Wi-Fi address only if current device status fails')
    parser.add_argument('--report', type=Path, default=ROOT / 'build/device-lab/mcp-deployment-check.json')
    args = parser.parse_args()
    recovered = False
    try:
        if args.recover_device:
            health = adapter.get_installation_status()
            if health.get('device_error') and health.get('runtime', {}).get('transport') == 'wifi':
                recovered = bool(adapter.discover_paired_device(update_connection=True).get('updated'))
        report = asyncio.run(verify(args.transport, args.url))
    except Exception:
        # Replace stale success evidence even when discovery/protocol calls fail.
        # Never persist raw exceptions that could contain private request data.
        report = {'passed': False, 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'scope': 'local_sdk_status_calls', 'mcp_transport': args.transport,
                  'error': 'Connection verification failed; check collector, pairing and LAN',
                  'target_ai_chat_verified': False, 'idle_wake_verified': False}
    report['paired_device_address_recovered'] = recovered
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    # Local evidence retains returned call IDs, but never claims they came from the AI chat.
    print(json.dumps({key: value for key, value in report.items() if key != 'sdk_verification_calls'}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError):
        print('Connection verification failed; check the local collector, device pairing and LAN.', file=sys.stderr)
        sys.exit(1)
