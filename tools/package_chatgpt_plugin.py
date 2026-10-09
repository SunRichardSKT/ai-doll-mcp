"""Build a machine-specific local MCP plugin ZIP without copying private runtime data.

This uses the portable Agent Plugins manifest. ChatGPT upload and tool
availability must be verified in the actual target chat; the ZIP is not a tunnel.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/SunRichardSKT/ai-doll-mcp'


def build_package(python: Path, output: Path) -> dict:
    python = python.resolve(strict=True)
    server = (ROOT / 'tools/companion_mcp.py').resolve(strict=True)
    if not python.is_file():
        raise ValueError('Python must be an executable file')
    manifest = {
        '$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
        'name': 'ai-doll-local', 'version': '0.1.1',
        'description': 'Local Windows MCP connection to the installed AI Doll service. Actual Chat support requires testing.',
        'author': {'name': 'SunRichardSKT'},
        'homepage': REPOSITORY, 'repository': REPOSITORY,
        'extensions': {'com.openai': {'interface': {
            'displayName': 'AI Doll Local',
            'shortDescription': 'Connect your installed doll service on this Windows PC',
            'longDescription': 'Reuse the current conversation and its model. Local MCP requires the installed project, Python dependencies and running collector. Ordinary Chat availability is not yet verified.',
            'developerName': 'SunRichardSKT', 'category': 'Productivity',
            'capabilities': ['Read', 'Write'],
            'websiteURL': REPOSITORY,
            'defaultPrompt': ['Check the doll installation and live device status using real tools.'],
        }}},
    }
    launcher = (ROOT/'tools/launch_companion_mcp.ps1').resolve(strict=True)
    mcp = {'$schema': 'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json',
           'mcpServers': {'ai_doll': {
        'type': 'stdio', 'command': 'powershell.exe',
        'args': ['-NoProfile', '-NonInteractive', '-File', str(launcher),
                 '-PythonExecutable', str(python)],
    }}}
    readme = '''# AI Doll Local — 本机插件测试包

这是本机 MCP 连接包，不是固件包、代码交付包或公网服务。
采用 OpenAI 文档推荐的根目录 plugin.json 与 mcp.json 格式，
明确声明 STDIO 传输类型。使用 Windows PowerShell 启动已安装的 Python。

1. 保留生成包时的项目目录和 Python，保持电脑娃娃服务运行。
2. 在桌面客户端的插件页面选择“上传插件压缩包”，上传此 ZIP。
3. 安装后新建普通 Chat，输入 @ 选择 AI Doll Local。
4. 要求实际调用 get_installation_status 与 doll_get_status，并返回真实状态。
5. 确认工具可用后才开始限时模拟按压测试，最后 end_interaction。

本包仅包含插件描述、启动配置和此说明。没有 Wi-Fi 密码、访问令牌、
个人日志、模型密钥或运行依赖。访问令牌仍由本机 MCP 在本机读取。
启动配置包含本机绝对路径；移动项目、换电脑或换 Python 后重新生成。
它不会安装 Python、启动采集服务、注册账号侧连接或建立隧道。

ZIP 上传成功不证明普通 Chat 可启动本机 MCP。若提示不支持 STDIO、
要求服务器 URL/已注册 MCP，或安装后仍无工具，保留实际错误，转用
平台支持的私有 Tunnel/远程连接；不要填写 GitHub 或 localhost 代替。
本机依赖不能由网页或手机运行，亦未验证空闲聊天的主动唤醒。

格式依据：https://developers.openai.com/plugins/build/plugins
普通 Chat 指南：项目 docs/CHAT_MCP.md
'''
    encode = lambda value: (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files = {
        'plugin.json': encode(manifest),
        'mcp.json': encode(mcp),
        'README.md': readme.encode('utf-8'),
    }
    # All payloads are generated here, never copied from build/device-lab.
    output = output.resolve()
    if output.exists():
        raise FileExistsError('Package already exists; choose a new output filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    with zipfile.ZipFile(output) as archive:
        if set(archive.namelist()) != set(files) or archive.testzip() is not None:
            raise ValueError('Plugin ZIP integrity check failed')
        if any(archive.read(name) != contents for name, contents in files.items()):
            raise ValueError('Plugin ZIP payload differs')
    return {'file': str(output), 'files': len(files), 'bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'format': 'agent-plugins-1.0.0', 'scope': 'this Windows installation',
            'chat_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--output', type=Path,
                        default=ROOT/'build/device-lab/AI_Doll_ChatGPT_Local_Test_v2.zip')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This package is for Windows desktop testing')
    print(json.dumps(build_package(args.python, args.output), ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
