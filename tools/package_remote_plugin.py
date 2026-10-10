"""Optional PRIVATE remote plugin ZIP, generated only from a verified live installation."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from chat_mcp_gateway import ROOT
from remote_mcp import CapabilityStore
from deploy_mcp import DEFAULT, config, verify
from private_storage import private_directory


def build_package(folder=DEFAULT, output=None):
    folder=Path(folder).resolve()
    cfg=config(folder)
    # Validate the actual endpoint now; a saved URL or uploaded ZIP is insufficient.
    check=verify(folder,calls=True)
    if not check.get('protocol_connected') or not check.get('trusted_https'):
        raise RuntimeError('Verify trusted HTTPS and real MCP status calls before packaging a private connection')
    output=Path(output or folder/'AI_Doll_Chat_PRIVATE.zip').resolve()
    if not output.is_relative_to(folder):
        raise ValueError('The credential-bearing plugin must stay in its private installation folder')
    if output.exists():raise FileExistsError('Choose a new private output filename')
    private_directory(output.parent)
    manifest={
        '$schema':'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
        'name':'ai-doll-chat','version':'0.1.0',
        'description':'Private MCP connection for doll history and timed interaction in the current conversation.',
        'author':{'name':'SunRichardSKT'},
        'extensions':{'com.openai':{'interface':{
            'displayName':'AI Doll Chat','shortDescription':'Doll history and interaction',
            'longDescription':'Use this verified private installation in your existing chat. The ZIP contains an access credential and must not be shared.',
            'developerName':'SunRichardSKT','category':'Productivity','capabilities':['Read','Write'] if cfg['profile']=='interaction' else ['Read'],
            'defaultPrompt':'Actually query the doll status and return verification.call_id.'}}}}
    mcp={'$schema':'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json',
         'mcpServers':{'ai_doll':{'type':'streamable-http','url':CapabilityStore(folder).url(cfg['origin'])}}}
    prompt=__import__('chat_mcp_gateway').doll_chat_companion()
    files={
        'plugin.json':json.dumps(manifest,ensure_ascii=False,indent=2),
        'mcp.json':json.dumps(mcp,ensure_ascii=False,indent=2),
        'skills/doll-interaction/SKILL.md':'---\nname: doll-interaction\ndescription: Use when the user queries doll history or explicitly requests timed body interaction in this conversation.\n---\n\n'+prompt,
        'README.md':'# 私人连接包\n\n含私密 MCP 地址，请勿公开、提交 GitHub 或转送。电脑和隧道必须运行。ZIP 只包装技能和连接，不部署服务。上传后在原 Chat 实际调用工具验收；SDK 通过不能替代普通 Chat 验收。\n'}
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,value in files.items():archive.writestr('ai-doll-chat/'+name,value.encode('utf-8'))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or set(archive.namelist())!={'ai-doll-chat/'+n for n in files}:raise RuntimeError('Private plugin ZIP failed integrity verification')
    return dict(file=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),private=True,ordinary_chat_verified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,default=DEFAULT)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:print(json.dumps(build_package(args.folder,args.output),ensure_ascii=False,indent=2))
    except Exception:
        print('Private package was not created. Verify the HTTPS connection and choose a new private output filename.')
        raise SystemExit(1)


if __name__=='__main__':main()
