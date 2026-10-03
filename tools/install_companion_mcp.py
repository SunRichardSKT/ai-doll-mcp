"""Generate portable MCP configuration; optionally register it in local Codex."""
import argparse
import json
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--codex', action='store_true', help='Install/update only ai_doll in the local Codex config')
    args = parser.parse_args()
    work = ROOT/'build/device-lab'
    work.mkdir(parents=True, exist_ok=True)
    server = {'command': sys.executable, 'args': [str(ROOT/'tools/companion_mcp.py')]}
    output = work/'mcp-client-config.json'
    output.write_text(json.dumps({'mcpServers': {'ai_doll': server}}, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.codex:
        path = pathlib.Path.home()/'.codex/config.toml'
        source = path.read_text(encoding='utf-8') if path.exists() else ''
        tomllib.loads(source)
        # Preserve every other table and all unrelated settings verbatim.
        updated = re.sub(r'(?ms)^\[mcp_servers\.ai_doll(?:\.[^\]]+)?\]\s*\n.*?(?=^\[|\Z)', '', source)
        updated += '\n[mcp_servers.ai_doll]\ncommand = '+json.dumps(server['command'])+'\nargs = '+json.dumps(server['args'])+'\nenabled = true\nstartup_timeout_sec = 20\ntool_timeout_sec = 60\n'
        parsed = tomllib.loads(updated)
        assert parsed['mcp_servers']['ai_doll']['command'] == sys.executable
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = path.with_suffix('.toml.before-companion')
        if not backup.exists():
            backup.write_text(source, encoding='utf-8')
        path.write_text(updated, encoding='utf-8')
        print('Registered ai_doll companion MCP in Codex. Reload MCP servers to discover tools.')
    print('Generated:', output)


if __name__ == '__main__':
    main()
