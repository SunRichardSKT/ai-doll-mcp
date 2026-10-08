"""Opt-in per-user Windows login startup. Dry-run never edits the registry."""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'AI_Doll_MCP_' + hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:12]


def startup_command(python=None, root=ROOT):
    executable = pathlib.Path(python or sys.executable).with_name('pythonw.exe')
    script = pathlib.Path(root)/'tools/run_background.py'
    if not executable.is_file() or not script.is_file():
        raise ValueError('A usable pythonw.exe and the companion background entry point are required')
    return subprocess.list2cmdline([str(executable.resolve()), str(script.resolve())])


def configure(action, dry_run=False):
    if action not in ('install', 'remove', 'status') or type(dry_run) is not bool:
        raise ValueError('Invalid startup action')
    if os.name != 'nt':
        raise ValueError('This startup helper is for Windows only')
    import winreg
    command = startup_command() if action != 'remove' else None
    stored = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_READ) as key:
            stored = winreg.QueryValueEx(key, NAME)[0]
    except FileNotFoundError:
        pass
    if not dry_run and action == 'install':
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command)
        stored = command
    elif not dry_run and action == 'remove':
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, NAME)
        except FileNotFoundError:
            pass
        stored = None
    return dict(action=action, dry_run=dry_run, enabled=stored is not None,
                matches_current_project=bool(command and stored == command),
                command=command, registry_value=NAME, applies_at='next Windows login',
                message='Uses saved transport and existing pairing; does not start or stop the current service')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'remove', 'status'))
    parser.add_argument('--dry-run', action='store_true')
    options = parser.parse_args()
    try:
        print(json.dumps(configure(options.action, options.dry_run), ensure_ascii=False, indent=2))
    except (OSError, ValueError):
        parser.exit(1, 'Unable to configure login startup; verify Python, project path and user registry access\n')
