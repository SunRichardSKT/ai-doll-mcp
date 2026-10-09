"""Strict destructive MCP arguments cannot be silently coerced into authorization."""
import pathlib
import site
import sys
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
import companion_mcp


class HistoryMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_destructive_flags_and_days_require_actual_boolean_and_integer(self):
        cases=[('delete_history',dict(preview_token='test',confirmed=value)) for value in ('true',1)]
        cases += [('set_history_retention',dict(enabled=value,days=90,confirmed=True)) for value in ('true',1)]
        cases += [('set_history_retention',dict(enabled=True,days=value,confirmed=True)) for value in ('90',True,90.5)]
        cases += [('set_history_retention',dict(enabled=True,days=90,confirmed=value)) for value in ('true',1)]
        with patch.object(companion_mcp,'call') as forwarded:
            for name,args in cases:
                with self.subTest(name=name,args=args),self.assertRaises(Exception):
                    await companion_mcp.mcp.call_tool(name,args)
            forwarded.assert_not_called()
    async def test_valid_explicit_confirmation_and_filters_reach_backend_unchanged(self):
        with patch.object(companion_mcp,'call',return_value={'deleted':True}) as forwarded:
            await companion_mcp.mcp.call_tool('delete_history',dict(preview_token='test',confirmed=True))
            forwarded.assert_called_once_with('delete_history',dict(preview_token='test',confirmed=True))
        with patch.object(companion_mcp,'call',return_value={'events':0}) as forwarded:
            await companion_mcp.mcp.call_tool('get_history_statistics',dict(filters={'body_part':'=data','time_scope':'unknown'}))
            forwarded.assert_called_once_with('get_history_statistics',dict(filters={'body_part':'=data','time_scope':'unknown'}))


if __name__=='__main__':unittest.main()
