"""Ensure old entry modules and new canonical imports share one implementation."""
import importlib
import subprocess
import sys
import unittest
from pathlib import Path

from _source_path import load


class SharedCoreTests(unittest.TestCase):
    def test_legacy_imports_are_the_identical_module(self):
        for name in ('interaction_bridge', 'input_observations', 'history_management', 'companion_experience'):
            with self.subTest(module=name):
                legacy = importlib.import_module(name)
                canonical = load('ai_doll.core.' + name)
                self.assertIs(legacy, canonical)
                self.assertIn('src', Path(canonical.__file__).parts)

    def test_isolated_runtime_loads_only_installed_source(self):
        tools = Path(__file__).resolve().parent
        script = ('import sys;sys.path.insert(0,' + repr(str(tools)) + ');'
                  'import interaction_bridge,companion_experience,history_management;'
                  'assert interaction_bridge.VERSION=="doll-bridge-2.25.0";'
                  'assert "src" in interaction_bridge.__file__;print("shared source OK")')
        result = subprocess.run([sys.executable, '-I', '-c', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
