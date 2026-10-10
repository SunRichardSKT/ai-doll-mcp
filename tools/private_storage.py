"""Atomic private installation files. Never print their contents."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def private_directory(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True).stdout
        sid = re.search(rb'S-1-5-[0-9-]+', identity)
        if not sid:
            raise RuntimeError('Cannot identify the current Windows user')
        subprocess.run(['icacls', str(folder), '/inheritance:r', '/grant:r',
                        '*'+sid[0].decode()+':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        folder.chmod(0o700)
    return folder


def write_private(path, contents):
    path = Path(path)
    private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != 'nt':
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, value):
    write_private(path, json.dumps(value, ensure_ascii=False, indent=2)+'\n')
