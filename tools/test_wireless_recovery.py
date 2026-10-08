"""Bare-board LAN discovery, stale-address recovery and duplicate service smoke test."""
import asyncio
import datetime
import hashlib
import json
import pathlib
import site
import subprocess
import sys
import urllib.request
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = ROOT/'.tools/mcp-test-sdk'
if SDK.exists():
    sys.path.insert(0, str(SDK)); site.addsitedir(str(SDK))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from device_discovery import discover_paired_device
from device_lab import CONFIG, WORK
from device_transport import create_device_link
from configure_startup import configure


async def main():
    checks = []
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    paired = discover_paired_device(config)
    assert paired and paired['verified'], 'Authenticated discovery did not find the paired ESP32'
    assert paired['firmware'] == 'doll-lab-2.5.0'
    checks.append('Real ESP32 UDP challenge/reply verified using the existing pairing')
    # A separate client starts with a stale address. It cannot open USB and writes
    # only its own disposable connection file, never the running owner's settings.
    scratch = WORK/'wireless-recovery-test-private.json'
    try:
        stale = '10.255.255.254' if paired['device_host'] != '10.255.255.254' else '10.255.255.253'
        with patch('device_transport.SerialLink', side_effect=AssertionError('Recovery opened USB')):
            link, info = create_device_link({'DOLL_TRANSPORT':'wifi', 'DOLL_DEVICE_HOST':stale}, CONFIG, scratch)
            link.timeout = 4  # Match production: a busy Wi-Fi board need not reply in 400 ms.
            status = link.exchange({'cmd':'status'})
            assert status['device_id'] == paired['device_id']
            assert info['device_host'] == paired['device_host']
            assert json.loads(scratch.read_text())['device_host'] == paired['device_host']
            assert status['discovery_active'] and status['sensor_mode'] == 'simulation'
            assert not status['physical_outputs_enabled']
            link.close()
        checks.append('Stale saved IP recovered to verified ESP32 address, persisted atomically, without USB')
    finally:
        scratch.unlink(missing_ok=True)

    async with stdio_client(StdioServerParameters(command=sys.executable,
                       args=[str(ROOT/'tools/companion_mcp.py')])) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert len(tools.tools) == 37
            discovered = await client.call_tool('discover_paired_device', {})
            assert not discovered.isError
            result = json.loads(discovered.content[0].text)
            assert result['found'] and result['verified'] and not result['updated']
            checks.append('Official MCP SDK sees 37 tools and read-only paired-device discovery works')
            session = await client.call_tool('get_interaction_status', {})
            assert not json.loads(session.content[0].text)['active_session'], 'Do not interrupt an active chat'

    protected = [WORK/'connection-private.json', WORK/'device-private.json', WORK/'companion-private.json']
    digests = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    duplicate = subprocess.run([sys.executable, str(ROOT/'tools/device_setup_server.py')],
                              capture_output=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
    assert duplicate.returncode == 0 and b'already running' in duplicate.stdout
    assert digests == {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    checks.append('A duplicate collector exits before changing pairing/connection state')
    before = configure('status')
    preview = configure('install', dry_run=True)
    assert preview['dry_run'] and configure('status') == before
    checks.append('Login-startup preview generated without enabling or altering registry settings')
    report = dict(passed=True, at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                  bridge='2.8.0', firmware='2.5.0', checks=checks,
                  limits=['No real router DHCP lease change was forced; recovery used a deliberately stale client address.',
                          'Windows login startup was previewed only, not enabled or verified across a login.',
                          'Standalone ESP32, no sensors or motor attached; no physical calibration or battery test.'])
    (WORK/'wireless-recovery-test.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
