"""Generate portable MCP configuration; optionally register it in local Codex."""
import argparse
import os
import json
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def client_config(client, server):
    """Use each official client's native configuration, with no model API proxy."""
    if client == 'deepseek':
        return [dict(id='ai-doll-mcp', name='@deepseek-ai/dsh-mcp-client',
                     config=dict(serverName='ai_doll', transport='stdio', **server))]
    if client in ('claude', 'gemini', 'local'):
        return {'mcpServers': {'ai_doll': dict(server)}}
    raise ValueError('Unsupported local MCP client')


def register_claude(path, server):
    """Merge this server into Claude Desktop, preserving other user settings."""
    if not path.parent.is_dir():
        raise ValueError('请先安装并启动一次 Claude Desktop，再生成连接配置。')
    source = path.read_text(encoding='utf-8-sig') if path.exists() else '{}'
    config = json.loads(source)
    if not isinstance(config, dict) or not isinstance(config.get('mcpServers', {}), dict):
        raise ValueError('Claude 配置格式不正确，请先修复；原文件保持。')
    config.setdefault('mcpServers', {})['ai_doll'] = server
    backup = path.with_suffix('.json.before-ai-doll')
    if path.exists() and not backup.exists():
        backup.write_text(source, encoding='utf-8')
    temporary = path.with_suffix('.json.ai-doll.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)
    return str(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--codex', action='store_true', help='Install/update only ai_doll in the local Codex config')
    parser.add_argument('--claude', action='store_true', help='Merge ai_doll into the Windows Claude Desktop config')
    parser.add_argument('--client', choices=['claude', 'gemini', 'deepseek', 'local'], default='local')
    args = parser.parse_args()
    work = ROOT/'build/device-lab'
    work.mkdir(parents=True, exist_ok=True)
    server = {'command': sys.executable, 'args': [str(ROOT/'tools/companion_mcp.py')]}
    output = work/'mcp-client-config.json'
    output.write_text(json.dumps(client_config(args.client, server), ensure_ascii=False, indent=2), encoding='utf-8')
    if args.claude:
        base = os.environ.get('APPDATA')
        if os.name != 'nt' or not base:
            raise ValueError('一键写入用于 Windows Claude Desktop；其他系统请合并生成的本机配置。')
        path = pathlib.Path(base)/'Claude/claude_desktop_config.json'
        print('Claude Desktop:', register_claude(path, server))
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
