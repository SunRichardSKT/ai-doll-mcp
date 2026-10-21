"""Verify source metadata can be rebuilt without overwriting an installed runtime."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import build_portable_python as builder


class PortableBuildTests(unittest.TestCase):
    def test_installed_runtime_is_rejected_before_network_or_cache_writes(self):
        with tempfile.TemporaryDirectory(prefix='AI Doll 构建保护 ') as folder:
            root = Path(folder)
            runtime = root / 'python'
            runtime.mkdir()
            binary = runtime / 'python.exe'
            binary.write_bytes(b'existing-runtime')
            (runtime / 'SHA256SUMS.txt').write_text('old-checksum\n', encoding='utf-8')
            with patch.object(builder, 'ROOT', root), patch.object(builder.urllib.request, 'urlopen') as download:
                with self.assertRaisesRegex(ValueError, 'Runtime already exists'):
                    builder.main()
                download.assert_not_called()
            self.assertEqual(binary.read_bytes(), b'existing-runtime')
            self.assertFalse((root / 'build').exists())

    def test_metadata_only_checkout_rebuilds_and_replaces_stale_checksums(self):
        with tempfile.TemporaryDirectory(prefix='AI Doll 元数据构建 ') as folder:
            root = Path(folder)
            runtime = root / 'python'
            runtime.mkdir()
            for name in ('README.md', 'RUNTIME.json', 'LICENSE.txt', 'SHA256SUMS.txt'):
                (runtime / name).write_text('old metadata\n', encoding='utf-8')
            cache = root / 'build/portable-python'
            cache.mkdir(parents=True)
            archive = cache / Path(builder.URL).name
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('python.exe', b'new-fixture-runtime')
                package.writestr('LICENSE.txt', b'fixture license')
                package.writestr('python314.zip', b'fixture standard library')

            def run(command, **kwargs):
                if '--target' in command:
                    target = Path(command[command.index('--target') + 1])
                    target.mkdir(parents=True, exist_ok=True)
                    (target / 'fixture.py').write_text('pass\n', encoding='utf-8')
                    (target / '__pycache__').mkdir(exist_ok=True)
                    (target / '__pycache__/fixture.pyc').write_bytes(b'cache')
                    (target / 'bin').mkdir(exist_ok=True)
                    (target / 'bin/nonportable-shim').write_bytes(b'shim')
                metadata = json.dumps({'python': builder.VERSION, 'packages': {'fixture': '1'}})
                return subprocess.CompletedProcess(command, 0, stdout=metadata)

            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.object(builder, 'ROOT', root), patch.object(builder, 'OFFICIAL_SHA256', digest), \
                    patch.object(builder.subprocess, 'run', side_effect=run), \
                    patch.object(builder.urllib.request, 'urlopen') as download, contextlib.redirect_stdout(io.StringIO()):
                builder.main()
                download.assert_not_called()

            metadata = json.loads((runtime / 'RUNTIME.json').read_text(encoding='utf-8'))
            self.assertEqual(metadata['archive_sha256'], digest)
            sums = (runtime / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
            names = []
            for line in sums:
                checksum, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((runtime / name).read_bytes()).hexdigest(), checksum)
                names.append(name)
            self.assertIn('python.exe', names)
            self.assertIn('RUNTIME.json', names)
            self.assertIn('Lib/site-packages/fixture.py', names)
            self.assertNotIn('SHA256SUMS.txt', names)
            self.assertFalse(any('__pycache__' in name for name in names))
            self.assertFalse((runtime / 'Lib/site-packages/bin').exists())


if __name__ == '__main__':
    unittest.main()
