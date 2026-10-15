"""Compatibility import; implementation lives in src/ai_doll/core."""
import sys as _sys
from _source_path import load as _load
_sys.modules[__name__] = _load("ai_doll.core.history_management")
