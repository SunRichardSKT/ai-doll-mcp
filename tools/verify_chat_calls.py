"""Correlate user-reported Chat call IDs with the current gateway's completed audit."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

from private_storage import write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'build/device-lab/secure-mcp'
CALL_ID = re.compile(r'[0-9a-f]{32}')


def correlate(folder, installation_call_id, device_call_id):
    folder = Path(folder).resolve()
    offered = {'get_installation_status': installation_call_id, 'doll_get_status': device_call_id}
    if (any(not isinstance(value, str) or not CALL_ID.fullmatch(value) for value in offered.values())
            or installation_call_id == device_call_id):
        raise ValueError('Provide two different 32-character call IDs returned by the target Chat')
    gateway = json.loads((folder / 'gateway/gateway.json').read_text(encoding='utf-8'))
    audit = [json.loads(line) for line in (folder / 'gateway/calls.jsonl').read_text(encoding='utf-8').splitlines()]
    sdk_file = folder / 'local-calls-private.json'
    if sdk_file.exists():
        sdk = json.loads(sdk_file.read_text(encoding='utf-8'))
        known_sdk = {entry.get('verification', {}).get('call_id')
                     for entry in sdk.get('status_calls', {}).values()}
        if known_sdk.intersection(offered.values()):
            raise ValueError('SDK verification IDs cannot replace target Chat IDs')
    matches = {}
    for name, call_id in offered.items():
        rows = [entry for entry in audit if entry.get('call_id') == call_id]
        if len(rows) != 1:
            raise ValueError('Call ID is absent or ambiguous in the gateway audit')
        row = rows[0]
        if (row.get('tool') != name or row.get('completed') is not True
                or row.get('run_id') != gateway.get('run_id')
                or row.get('profile') != gateway.get('profile') or row.get('execution_may_continue')):
            raise ValueError('Tool, success state or current server instance does not match')
        matches[name] = row
    proof = dict(scope='user_reported_ordinary_chat_status_calls', status_calls_correlated=True,
                 checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 run_id=gateway['run_id'], profile=gateway['profile'], calls=matches,
                 interaction_feedback_verified=False, idle_wake_verified=False)
    write_json(folder / 'chat-status-acceptance-private.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=DEFAULT)
    parser.add_argument('--installation-call-id', required=True)
    parser.add_argument('--device-call-id', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(correlate(args.folder, args.installation_call_id, args.device_call_id), indent=2))
    except (OSError, ValueError, KeyError):
        parser.exit(1, 'Target Chat call IDs did not match the current completed audit; no acceptance recorded.\n')
