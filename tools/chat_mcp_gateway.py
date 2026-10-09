"""Loopback Streamable HTTP adapter for the existing doll collector.

The status profile has two filtered read-only tools. The interaction profile
reuses existing MCP functions; it is intended for a private host connection.
This entrypoint never creates a public tunnel or registers a ChatGPT plugin.
"""
import argparse
import asyncio
import datetime as dt
import functools
import inspect
import json
from pathlib import Path
import re
import threading
import uuid
from typing import Any
from urllib.parse import urlsplit

import companion_mcp as adapter
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

ROOT = Path(__file__).resolve().parents[1]
STATUS_TOOLS = ('get_installation_status', 'doll_get_status')
INTERACTION_TOOLS = STATUS_TOOLS + (
    'get_channel_capabilities', 'get_channel_config',
    'get_persona', 'get_feedback_preferences',
    'start_interaction', 'get_interaction_status',
    'get_interaction_device_events', 'end_interaction',
    'query_device_history', 'summarize_interactions', 'get_history_statistics',
)
PROFILES = {'status': STATUS_TOOLS, 'interaction': INTERACTION_TOOLS}


def filtered_status(name, data):
    keys = ('device_id', 'firmware', 'wifi_connected', 'sensor_mode',
            'physical_outputs_enabled')
    if name == 'doll_get_status':
        return {key: data.get(key) for key in keys}
    device = data.get('device')
    return {
        'bridge': data.get('bridge'), 'python': data.get('python'),
        'database_open': data.get('database_open'),
        'runtime': {
            'transport': data.get('runtime', {}).get('transport'),
            'local_service_tool_count': data.get('runtime', {}).get('tool_count'),
        },
        'device': {key: device.get(key) for key in keys} if isinstance(device, dict) else None,
        'device_error': 'Device status unavailable' if data.get('device_error') else None,
        'collector_error': 'Collector unavailable' if data.get('collector_error') else None,
        'client_registration': 'not_inspected', 'host_event_support': 'not_verified',
        'secrets_included': False,
    }


def get_installation_status() -> dict:
    """Read filtered collector/device health. A call is not proof of idle chat wake-up."""
    return filtered_status('get_installation_status', adapter.get_installation_status())


def doll_get_status() -> dict:
    """Read actual device identity, firmware, Wi-Fi, simulation and output state."""
    return filtered_status('doll_get_status', adapter.doll_get_status())


def start_interaction(chat_id: str, idle_timeout_sec: int = 300) -> dict:
    """Start only on user intent; supply this chat's stable unique ID, never steal another chat's session."""
    if not chat_id.strip() or chat_id == 'main':
        raise ValueError('Use a stable unique chat_id, not the shared default main')
    return adapter.start_interaction(chat_id=chat_id, idle_timeout_sec=idle_timeout_sec)


def doll_chat_companion() -> str:
    """Use doll input in the current chat with this profile's tools."""
    return adapter.doll_chat_companion().replace(
        'get_installation_status(client_kind="stdio")', 'get_installation_status()')


def create_gateway(profile='status', port=8771, folder=None, public_origin=None):
    if profile not in PROFILES:
        raise ValueError('Unknown gateway profile')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Port must be in 1024..65535')
    hosts = ['127.0.0.1:*', 'localhost:*', '[::1]:*']
    origins = ['http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*']
    if public_origin:
        parsed = urlsplit(public_origin)
        if profile != 'status':
            raise ValueError('Public anonymous access is supported only for the two status tools; use a private connection for interaction')
        if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/') or not parsed.hostname
                or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', parsed.hostname)):
            raise ValueError('Provide one exact HTTPS origin, without path or credentials')
        external_port = parsed.port or 443
        hosts.extend([parsed.hostname + ':' + str(external_port), parsed.netloc])
        public_origin = 'https://' + parsed.netloc
        origins.append(public_origin)
    folder = Path(folder or ROOT / 'build/device-lab/chat-gateway')
    folder.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    names = PROFILES[profile]
    instructions = (adapter.mcp.instructions +
        ' This is a loopback-only Streamable HTTP adapter, not a public service or a '
        'registered client connection. Return verification.call_id when verifying calls. '
        'Only the listed profile tools are available. Simulate from the local device '
        'settings page; simulation and physical output tools are not exposed here.'
        if profile == 'interaction' else
        'This status profile has only two filtered read-only tools. It cannot read '
        'persona, history or interaction events, start sessions or control hardware. '
        'Actually call both tools and return verification.call_id to test a connection.'
    )
    server = FastMCP('AI Doll Chat ' + profile.title(), instructions=instructions,
                     host='127.0.0.1', port=port, stateless_http=True,
                     json_response=True, max_request_body_size=16384, log_level='WARNING',
                     transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins))
    slots = asyncio.Semaphore(4)
    log_lock = threading.Lock()

    def register(name, function):
        @functools.wraps(function)
        async def invoke(*args, **kwargs):
            call_id = uuid.uuid4().hex
            entry = {'run_id': run_id, 'call_id': call_id, 'tool': name,
                     'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                     'profile': profile, 'completed': False}
            acquired = False
            worker = None
            try:
                try:
                    await asyncio.wait_for(slots.acquire(), timeout=2)
                    acquired = True
                except asyncio.TimeoutError:
                    raise RuntimeError('Gateway busy; this operation was not started') from None
                # Existing bounded waits and urllib calls are synchronous. Keep the
                # HTTP event loop free so another chat can check/end its session.
                worker = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
                result = await asyncio.shield(worker)
                result = dict(result)
                result['verification'] = {
                    'run_id': run_id, 'call_id': call_id, 'at_utc': entry['at_utc'],
                    'gateway_profile': profile, 'exposed_tool_count': len(names),
                }
                entry['completed'] = True
                return result
            except asyncio.CancelledError:
                # Cancellation cannot retract a request already sent to the collector.
                # Do not restart a session without inspecting its actual state.
                raise
            except Exception:
                raise RuntimeError('Local doll operation failed; check collector, Wi-Fi and session state') from None
            finally:
                if acquired:
                    if worker is not None and not worker.done():
                        entry['execution_may_continue'] = True
                        # A disconnected HTTP client must not release capacity while
                        # its already-issued collector operation is still running.
                        def finish_worker(task):
                            slots.release()
                            if not task.cancelled():
                                task.exception()
                        worker.add_done_callback(finish_worker)
                    else:
                        slots.release()
                with log_lock, (folder / 'calls.jsonl').open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(entry) + '\n')

        invoke.__signature__ = inspect.signature(function).replace(return_annotation=dict[str, Any])
        server.add_tool(invoke, name=name, annotations=ToolAnnotations(
            readOnlyHint=name not in {'start_interaction', 'end_interaction'},
            destructiveHint=False, idempotentHint=True, openWorldHint=False))

    for name in names:
        function = globals().get(name) or getattr(adapter, name)
        register(name, function)
    if profile == 'interaction':
        server.prompt()(doll_chat_companion)
    metadata = {
        'run_id': run_id, 'profile': profile, 'tools': list(names),
        'local_url': f'http://127.0.0.1:{port}/mcp', 'public_endpoint_created': False,
        'configured_public_origin': public_origin,
        'client_registration': 'not_inspected', 'host_event_support': 'not_verified',
        'log': str(folder / 'calls.jsonl'),
    }
    (folder / 'gateway.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='status')
    parser.add_argument('--port', type=int, default=8771)
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--public-origin', help='Exact HTTPS origin for status-only forwarding; does not start a tunnel')
    args = parser.parse_args()
    create_gateway(args.profile, args.port, args.folder, args.public_origin).run(transport='streamable-http')


if __name__ == '__main__':
    main()
