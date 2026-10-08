"""Find an already-paired LAN device, optionally save its authenticated address."""
import argparse
import json

from device_lab import CONFIG, WORK
from device_discovery import discover_paired_device
from device_transport import save_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', action='store_true', help='Explicitly switch saved transport to Wi-Fi')
    args = parser.parse_args()
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
        found = discover_paired_device(config)
        if not found:
            parser.exit(1, 'No authenticated reply; check pairing, power, same LAN and UDP broadcast access\n')
        if args.save:
            path = WORK/'connection-private.json'
            saved = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
            save_connection(path, 'wifi', found['device_host'], saved.get('serial_port', 'COM3'))
        print(json.dumps(dict(found, saved=args.save), ensure_ascii=False, indent=2))
    except (OSError, ValueError):
        parser.exit(1, 'Discovery could not run; verify the existing local pairing configuration\n')


if __name__ == '__main__':
    main()
