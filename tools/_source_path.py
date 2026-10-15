"""Resolve this installation's own source package without adding third-party wheels."""
import importlib
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'src'

def load(name):
    if not name.startswith('ai_doll.') or not SOURCE.is_dir():
        raise ImportError('AI Doll source is missing; extract the complete package including src/')
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    return importlib.import_module(name)
