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
from pydantic import StrictInt

ROOT = Path(__file__).resolve().parents[1]
STATUS_TOOLS = ('get_installation_status', 'doll_get_status')
INTERACTION_TOOLS = STATUS_TOOLS + (
    'get_channel_capabilities', 'get_channel_config',
    'get_persona', 'get_feedback_preferences',
    'start_interaction', 'get_interaction_status',
    'get_interaction_device_events', 'end_interaction',
    'query_device_history', 'summarize_interactions', 'get_history_statistics',
)
HISTORY_TOOLS = tuple(name for name in INTERACTION_TOOLS if name not in {
    'start_interaction', 'get_interaction_status', 'get_interaction_device_events', 'end_interaction'})
PROFILES = {'status': STATUS_TOOLS, 'history': HISTORY_TOOLS, 'interaction': INTERACTION_TOOLS}


class ProfileMCP(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()
        return [tool.model_copy(update={'securitySchemes': tool.meta['securitySchemes']}) for tool in tools]


def normalize_public_origin(origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or not parsed.hostname
            or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', parsed.hostname)):
        raise ValueError('Provide one exact HTTPS origin, without path or credentials')
    parsed.port  # Validate the optional port before creating any private state.
    return 'https://' + parsed.netloc


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
        'last_sync': data.get('last_sync'),
        'client_registration': 'not_inspected', 'host_event_support': 'not_verified',
        'secrets_included': False,
    }


def get_installation_status() -> dict:
    """Read filtered collector/device health. A call is not proof of idle chat wake-up."""
    return filtered_status('get_installation_status', adapter.get_installation_status())


def doll_get_status() -> dict:
    """Read actual device identity, firmware, Wi-Fi, simulation and output state."""
    return filtered_status('doll_get_status', adapter.doll_get_status())


def start_interaction(chat_id: str, idle_timeout_sec: StrictInt = 300, duration_sec: StrictInt | None = None) -> dict:
    """Start only on user intent; supply this chat's stable unique ID, never steal another chat's session."""
    if not chat_id.strip() or chat_id == 'main':
        raise ValueError('Use a stable unique chat_id, not the shared default main')
    return adapter.start_interaction(chat_id=chat_id, idle_timeout_sec=idle_timeout_sec, duration_sec=duration_sec)


def get_channel_config() -> dict:
    """Read the collector's cached channel types/body labels, including saved time and sync quality."""
    return adapter.call('get_cached_channel_config', {})


def get_channel_capabilities() -> dict:
    """Read cached capabilities; unavailable before the collector has first synchronized them."""
    return adapter.call('get_cached_channel_capabilities', {})


def private_interaction_events(session_id: str, chat_id: str, after: StrictInt = 0,
                               limit: StrictInt = 50, wait_seconds: StrictInt = 0) -> dict:
    """Read new events only for this session AND this chat. Save next_cursor; each wait <=20 seconds."""
    if not chat_id.strip() or chat_id=='main':raise ValueError('Use this chat\'s unique chat_id')
    return adapter.get_interaction_device_events(session_id,after,limit,wait_seconds,chat_id=chat_id)


def private_end_interaction(session_id: str, chat_id: str) -> dict:
    """End only the session belonging to this chat. Other chats cannot end it."""
    if not chat_id.strip() or chat_id=='main':raise ValueError('Use this chat\'s unique chat_id')
    return adapter.call('end_interaction',dict(session_id=session_id,chat_id=chat_id))


def doll_chat_companion() -> str:
    """Use doll input in the current chat with this profile's tools."""
    return adapter.doll_chat_companion().replace(
        'get_installation_status(client_kind="stdio")', 'get_installation_status()') + '\n远程私密地址连接读取新事件和结束会话时，必须一并提供本聊天原始 chat_id 与 session_id，不能使用其他聊天的标识。\n'


def create_gateway(profile='status', port=8771, folder=None, public_origin=None,
                   capability_store=None):
    if profile not in PROFILES:
        raise ValueError('Unknown gateway profile')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Port must be in 1024..65535')
    hosts = ['127.0.0.1:*', 'localhost:*', '[::1]:*']
    origins = ['http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*']
    if public_origin:
        public_origin = normalize_public_origin(public_origin)
        parsed = urlsplit(public_origin)
        if profile != 'status' and capability_store is None:
            raise ValueError('Public anonymous access is supported only for the two status tools; use a private connection for interaction')
        external_port = parsed.port or 443
        hosts.extend([parsed.hostname + ':' + str(external_port), parsed.netloc])
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
        'Read only archived history, cached channel configuration, persona and preferences. '
        'Do not start sessions or control hardware. Keep the current conversation/model. '
        'Return verification.call_id when verifying tools.' if profile == 'history' else
        'This status profile has only two filtered read-only tools. It cannot read '
        'persona, history or interaction events, start sessions or control hardware. '
        'Actually call both tools and return verification.call_id to test a connection.'
    )
    if capability_store is not None:
        instructions = adapter.mcp.instructions + ' This private-address MCP uses no account login. Return verification.call_id when verifying calls. Only listed tools are available. Include the original chat_id AND session_id when reading interaction events or ending a session; never use IDs from another chat. For a 60-second test pass duration_sec=60 to start_interaction.'
    server = ProfileMCP('AI Doll Chat ' + profile.title(), instructions=instructions,
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
        schemes = [{'type': 'noauth'}]
        server.add_tool(invoke, name=name, meta={'securitySchemes': schemes}, annotations=ToolAnnotations(
            readOnlyHint=name not in {'start_interaction', 'end_interaction'},
            destructiveHint=False, idempotentHint=True, openWorldHint=False))

    for name in names:
        private_functions = {'get_interaction_device_events':private_interaction_events,'end_interaction':private_end_interaction}
        function = private_functions[name] if capability_store is not None and name in private_functions else globals().get(name) or getattr(adapter, name)
        register(name, function)
    if profile == 'interaction':
        server.prompt()(doll_chat_companion)
    metadata = {
        'run_id': run_id, 'profile': profile, 'tools': list(names),
        'local_url': f'http://127.0.0.1:{port}/mcp', 'public_endpoint_created': False,
        'configured_public_origin': public_origin,
        'authentication': 'private_address' if capability_store is not None else 'none',
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
