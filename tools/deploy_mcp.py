"""Install/configure/start/status/stop/reset the private-address Sakura MCP deployment."""
import argparse
import asyncio
import datetime as dt
import getpass
import json
import logging
from pathlib import Path
import socket
import sys
import time

# Load the pinned SDK in the same way as the existing STDIO adapter.
import companion_mcp
from chat_mcp_gateway import normalize_public_origin, PROFILES, ROOT, STATUS_TOOLS
from remote_mcp import CapabilityStore
from owned_processes import alive, launch, record, terminate, OwnedChildJob
from private_storage import private_directory, write_json
from sakura_frp import SakuraAPI, install_client, configure_tunnel
from service_lifecycle import ServiceLease, ServiceAlreadyRunning

DEFAULT = ROOT/'build/device-lab/remote-mcp'


def read_json(path, default=None):
    if not Path(path).exists(): return default
    return json.loads(Path(path).read_text(encoding='utf-8'))


def config(folder):
    data = read_json(Path(folder)/'sakura-private.json')
    if not data:
        raise ValueError('Complete first-time Sakura configuration locally before starting the remote connection')
    data['origin'] = normalize_public_origin(data['origin'])
    mode = data.get('tunnel_management', 'project')
    if data.get('profile') not in PROFILES or mode not in ('project', 'client'):
        raise ValueError('Invalid private Sakura configuration')
    if mode == 'client':
        if 'token' in data:
            raise ValueError('Client-managed tunnels must not contain an access token')
    elif (type(data.get('tunnel_id')) is not int or data['tunnel_id'] <= 0
          or not isinstance(data.get('token'), str) or not data['token'].strip()
          or any(ord(c) < 33 for c in data['token'])):
        raise ValueError('Invalid private Sakura configuration')
    return data


def occupied(port=8771):
    with socket.socket() as client:
        client.settimeout(.3)
        return client.connect_ex(('127.0.0.1',port))==0


def save_connection(folder, cfg):
    store = CapabilityStore(folder)
    write_json(Path(folder)/'chatgpt-connection-private.json',dict(
        name='AI Doll',url=store.url(cfg['origin']),authentication='none',
        profile=cfg['profile'],tools=len(PROFILES[cfg['profile']]),
        note='This full URL is a credential. Do not publish or share it.'))


async def probe_url(url, profile, calls=False):
    """Official SDK; normal HTTPS trust validation, no redirects or credential logging."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx
    # This is a diagnostic hint, never an authentication or client identity check.
    probe_headers = {'x-ai-doll-probe': 'verification' if calls else 'health'}
    async with httpx.AsyncClient(timeout=httpx.Timeout(25,connect=8),follow_redirects=False,
                                verify=True,headers=probe_headers) as http:
        async with streamable_http_client(url,http_client=http) as (read,write,_):
            async with ClientSession(read,write) as client:
                initialized = await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                if names != set(PROFILES[profile]): raise ValueError('Unexpected MCP tool profile')
                result = dict(protocol_connected=True,protocol_version=initialized.protocolVersion,
                              tool_count=len(names),sdk_verified=True,ordinary_chat_verified=False,
                              trusted_https=url.startswith('https://'),status_calls={})
                if calls:
                    for name in STATUS_TOOLS:
                        response = await client.call_tool(name,{})
                        data = response.structuredContent
                        if response.isError or not isinstance(data,dict) or not data.get('verification',{}).get('call_id'):
                            raise ValueError('Actual MCP status call failed')
                        result['status_calls'][name] = data
                return result


def verify(folder, remote=True, calls=False):
    cfg = config(folder)
    store = CapabilityStore(folder)
    url = store.url(cfg['origin']) if remote else 'http://127.0.0.1:8771/'+store.key()+'/mcp'
    # SDK/httpx logging contains request URLs. Deployment deliberately keeps none.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    report = dict(checked_at=time.time(),scope='remote_sdk' if remote else 'loopback_sdk',
                  protocol_connected=False,trusted_https=False,ordinary_chat_verified=False)
    try:
        report.update(asyncio.run(asyncio.wait_for(probe_url(url,cfg['profile'],calls),timeout=35)))
        if calls and not remote:
            audit = [json.loads(line) for line in (Path(folder)/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
            for value in report['status_calls'].values():
                verification = value['verification']
                if not any(entry.get('call_id')==verification['call_id'] and entry.get('run_id')==verification['run_id']
                           and entry.get('completed') for entry in audit):
                    raise ValueError('Call IDs did not match local server audit')
            report['call_ids_correlated'] = True
    except Exception:
        report.update(protocol_connected=False,trusted_https=False,
                      error='Connection verification failed; check service, tunnel, DNS and trusted certificate')
    finally:
        logging.disable(previous_logging)
    # Periodic discovery must not erase the user's actual status-call evidence.
    filename = ('remote-check.json' if calls else 'remote-health-check.json') if remote else 'loopback-check.json'
    write_json(Path(folder)/filename, report)
    return report


def status(folder):
    state = read_json(Path(folder)/'processes.json',{})
    recent = read_json(Path(folder)/'deployment-status.json',{})
    processes = {name:alive(value) for name,value in state.items()}
    cfg = read_json(Path(folder)/'sakura-private.json', {})
    mode = cfg.get('tunnel_management', 'project')
    connected = bool(processes.get('supervisor') and processes.get('gateway')
                     and (mode == 'client' or processes.get('tunnel'))
                     and recent.get('protocol_connected') and time.time()-recent.get('checked_at',0)<90)
    return dict(configured=(Path(folder)/'sakura-private.json').is_file(),
                processes=processes,remote_connected=connected,
                trusted_https=connected and recent.get('trusted_https',False),
                last_check=recent.get('checked_at'),retry_seconds=recent.get('retry_seconds'),
                error=recent.get('error'),ordinary_chat_verified=False,
                tunnel_management=mode,external_client_managed=mode == 'client')


def cleanup_children(folder, state):
    for name in ('tunnel','gateway'):
        if value := state.get(name): terminate(value)
        state.pop(name,None)
    write_json(Path(folder)/'processes.json',state)


def stop(folder):
    folder = Path(folder)
    state = read_json(folder/'processes.json',{})
    write_json(folder/'stop.json',dict(requested_at=time.time()))
    for _ in range(100):
        if not alive(state.get('supervisor')): break
        time.sleep(.1)
    # Fallback touches only exact creation-time/executable identities we recorded.
    state = read_json(folder/'processes.json',state)
    cleanup_children(folder,state)
    terminate(state.get('supervisor'))
    write_json(folder/'processes.json',{})
    write_json(folder/'deployment-status.json',dict(protocol_connected=False,trusted_https=False,checked_at=time.time(),stopped=True))
    return status(folder)


def start(folder):
    folder = Path(folder).resolve()
    private_directory(folder)
    cfg = config(folder)
    with ServiceLease(folder/'control.lock'):
        current = status(folder)
        if current['processes'].get('supervisor'):
            return dict(current,reused=True)
        state = read_json(folder/'processes.json',{})
        cleanup_children(folder,state)
        if occupied():
            raise RuntimeError('Port 8771 belongs to an unowned service; it will not be stopped or reused')
        folder.joinpath('stop.json').unlink(missing_ok=True)
        save_connection(folder,cfg)
        child, value = launch([sys.executable,str(ROOT/'tools/deploy_mcp.py'),'supervise','--folder',str(folder)],ROOT)
        write_json(folder/'processes.json',dict(supervisor=value))
        # Readiness is checked by the supervisor. Starting a PID alone is not connected.
        for _ in range(20):
            if child.poll() is not None:
                raise RuntimeError('Deployment supervisor failed; inspect local deployment status')
            if status(folder)['processes'].get('gateway'): break
            time.sleep(.25)
        return dict(status(folder),reused=False)


def supervise(folder):
    previous_logging = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        return _supervise(folder)
    finally:
        logging.disable(previous_logging)


def _supervise(folder):
    folder = Path(folder).resolve()
    with ServiceLease(folder/'supervisor.lock'):
        # Wait for the launching controller to finish recording this supervisor.
        for _ in range(40):
            state = read_json(folder/'processes.json',{})
            if alive(state.get('supervisor')) and state['supervisor']['pid']==__import__('os').getpid(): break
            time.sleep(.1)
        else: raise RuntimeError('Supervisor ownership was not recorded')
        job = OwnedChildJob()
        retry = 1
        try:
            while not (folder/'stop.json').exists():
                try:
                    cfg = config(folder)
                    if not alive(state.get('gateway')):
                        if occupied(): raise RuntimeError('Unowned service on MCP port')
                        _, state['gateway'] = launch([sys.executable,str(ROOT/'tools/remote_mcp.py'),
                            '--folder',str(folder),'--public-origin',cfg['origin'],'--profile',cfg['profile']],ROOT)
                        write_json(folder/'processes.json',state)
                    if cfg.get('tunnel_management', 'project') == 'project' and not alive(state.get('tunnel')):
                        executable, version = install_client(folder/'client')
                        private_config = configure_tunnel(SakuraAPI(cfg['token']),cfg['tunnel_id'],version,folder)
                        _, state['tunnel'] = launch([str(executable.resolve()),'-c',str(private_config.resolve()),
                                                    '--disable_log_color','--log_level','error','--no_check_update'],folder)
                        write_json(folder/'processes.json',state)
                    check = verify(folder,remote=True)
                    if not check['protocol_connected']:
                        raise RuntimeError('Trusted HTTPS MCP not ready')
                    retry = 1
                    write_json(folder/'deployment-status.json',dict(check,retry_seconds=0))
                    delay = 30
                except Exception:
                    write_json(folder/'deployment-status.json',dict(protocol_connected=False,trusted_https=False,
                        checked_at=time.time(),retry_seconds=retry,
                        error='Remote MCP unavailable; check the local setup, designated tunnel, network and certificate'))
                    delay, retry = retry, min(60,retry*2)
                    # A dead client is retried; a live Sakura client reconnects internally.
                # Short slices allow stop/reset to remain responsive during backoff.
                until = time.monotonic()+delay
                while time.monotonic()<until and not (folder/'stop.json').exists(): time.sleep(.25)
        finally:
            cleanup_children(folder,state)
            state.pop('supervisor',None)
            write_json(folder/'processes.json',state)
            write_json(folder/'deployment-status.json',dict(protocol_connected=False,trusted_https=False,stopped=True,checked_at=time.time()))
            job.close()


def reset_address(folder):
    folder = Path(folder)
    CapabilityStore(folder,allow_corrupt=True).reset()
    cfg = read_json(folder/'sakura-private.json')
    if cfg: save_connection(folder,config(folder))
    # Rotation invalidates prior verification; do not display stale success.
    write_json(folder/'deployment-status.json',dict(protocol_connected=False,trusted_https=False,checked_at=time.time(),address_reset=True))
    return dict(reset=True,old_address_valid=False,connection_file=str(folder/'chatgpt-connection-private.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('configure','download','start','status','stop','reset-address','verify','address','supervise'))
    parser.add_argument('--folder',type=Path,default=DEFAULT)
    parser.add_argument('--profile',choices=PROFILES,default='interaction')
    parser.add_argument('--local',action='store_true',help='Verify loopback instead of HTTPS (SDK evidence only)')
    parser.add_argument('--client-managed', action='store_true',
                        help='Configure an existing Sakura client to manage forwarding; do not request or store its token')
    args = parser.parse_args()
    folder = args.folder.resolve()
    try:
        if args.action=='configure':
            if status(folder)['processes'].get('supervisor'): raise ValueError('Stop this deployment before changing Sakura configuration')
            origin = normalize_public_origin(input('Sakura HTTPS origin (include port if needed): ').strip())
            if args.client_managed:
                cfg = dict(origin=origin, profile=args.profile, tunnel_management='client')
            else:
                tunnel_id = int(input('Dedicated tunnel ID: ').strip())
                token = getpass.getpass('Sakura access token (hidden, saved locally): ').strip()
                if tunnel_id<=0 or not token or any(ord(c)<33 for c in token): raise ValueError('Invalid token or tunnel ID')
                cfg = dict(origin=origin, tunnel_id=tunnel_id, token=token, profile=args.profile)
            write_json(folder/'sakura-private.json', cfg)
            save_connection(folder,config(folder))
            result = dict(configured=True,profile=args.profile,connection_file=str(folder/'chatgpt-connection-private.json'))
        elif args.action=='download':
            _,version = install_client(folder/'client'); result = dict(client_verified=True,version=version)
        elif args.action=='start': result = start(folder)
        elif args.action=='stop':
            with ServiceLease(folder/'control.lock'): result = stop(folder)
        elif args.action=='status': result = status(folder)
        elif args.action=='reset-address':
            with ServiceLease(folder/'control.lock'): result = reset_address(folder)
        elif args.action=='verify':
            result = verify(folder,remote=not args.local,calls=True)
            # Full status evidence goes only to private report, console is minimal.
            result = {k:v for k,v in result.items() if k!='status_calls'}
        elif args.action=='address':
            print(CapabilityStore(folder).url(config(folder)['origin']))
            return
        else:
            supervise(folder); return
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.action=='verify' and not result['protocol_connected']: raise SystemExit(1)
    except Exception:
        print('Operation failed. Check the local configuration and docs/REMOTE_MCP.md; no credentials were printed.',file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__': main()
