"""Deprecated build entry: produce current unified artifacts, never another patch ZIP."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Build the current complete delivery')
    args = parser.parse_args()
    if args.full:
        from package_companion import main as build
        build()
    else:
        from package_operit import build
        print(json.dumps(build(), indent=2))


if __name__ == '__main__':
    main()
