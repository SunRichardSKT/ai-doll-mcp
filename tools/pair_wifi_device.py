"""Pair a LAN device with a privately entered token; preserve existing credentials."""
import argparse
import getpass
import json
from device_lab import CONFIG, WORK
from device_transport import WifiLink, save_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Device LAN IPv4 address')
    parser.add_argument('--new-token', action='store_true', help='Enter a replacement token privately')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig')) if CONFIG.exists() else {}
    if args.new_token or not config.get('mcp_token'):
        config['mcp_token'] = getpass.getpass('Device MCP token (hidden, copied from device settings): ')
    link = WifiLink(args.host, config)
    status = link.exchange({'cmd': 'status'})
    config['device_id'] = status['device_id']
    config['state'] = status
    WORK.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(CONFIG)
    save_connection(WORK/'connection-private.json', 'wifi', link.host)
    print('Paired ' + status['device_id'] + ' over Wi-Fi at ' + link.host)
    print('Token remains in local ignored configuration. No USB port was opened.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError):
        raise SystemExit('Pairing failed. Check LAN IP, device power, MCP switch and token; existing pairing is unchanged.')
