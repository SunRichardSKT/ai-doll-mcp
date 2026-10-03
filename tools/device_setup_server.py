"""Loopback-only USB provisioning page. Wi-Fi password is forwarded, never logged/saved on PC."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import json,secrets,threading,time,os,hmac,traceback
import asyncio
from urllib.parse import urlsplit,parse_qs
from mcp_events_adapter import MCPEventsAdapter
from webhook_delivery import webhook_worker
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from companion import Companion
from device_lab import SerialLink,CONFIG,WORK
SERIAL_LINK=SerialLink(os.environ.get("DOLL_SERIAL_PORT","COM3"))
def exchange(command):
    return SERIAL_LINK.exchange(command)
COMPANION=None
COMPANION_TOKEN=""
EVENTS_ADAPTER=None
TOOLS_CACHE=None
STREAM_CLIENTS={}
STREAM_LOCK=threading.Lock()
LOCK=threading.Lock();CSRF=secrets.token_hex(24)

def bridge_tools():
    global TOOLS_CACHE
    if TOOLS_CACHE is None:
        from companion_mcp import mcp
        TOOLS_CACHE=[t.model_dump(exclude_none=True) for t in asyncio.run(mcp.list_tools())]
    return TOOLS_CACHE

def bridge_subscribe(data):
    required={'target_id','session_id','device_id'}
    if not isinstance(data,dict) or set(data)-required-{'ttl_sec','policy','feedback'} or not required<=set(data):
        raise ValueError('target_id/session_id/device_id required')
    status=COMPANION.device('doll_get_status',{})
    if data['device_id']!=status['device_id']:raise ValueError('Unknown device')
    return COMPANION.bridge.subscribe('local-owner',**data)
PAGE=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>共感娃娃 USB 配网</title><style>body{font:17px system-ui;max-width:650px;margin:50px auto;padding:24px;background:#f3f1e9;color:#263e33}section{background:white;padding:28px;border-radius:20px}input,select,button{width:100%;box-sizing:border-box;padding:14px;margin:8px 0;border:1px solid #bccabe;border-radius:8px}button{background:#2b6249;color:white;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><section><h1>共感娃娃 · USB 配网</h1><p><a href="/companion">打开互动记录与部位设置</a></p><p>ESP32-C3 已接入电脑。请输入 2.4 GHz Wi-Fi 信息。</p><button id="scan" onclick="scanWifi()">扫描附近 Wi-Fi</button><select id="networks" onchange="document.querySelector('#ssid').value=this.value"><option value="">请选择网络，或在下方手动输入</option></select><small id="scanHint">由设备扫描附近的 2.4 GHz Wi-Fi。</small><input id="ssid" placeholder="Wi-Fi 名称（也可手动输入）" maxlength="32"><input id="password" type="password" placeholder="Wi-Fi 密码" maxlength="63"><button id="save" onclick="join()">保存到设备并连接</button><p>密码直接通过 USB 发给设备，电脑不保存，也不输出到日志。</p><pre id="status">读取设备状态…</pre><h2>MCP 实机测试</h2><button onclick="simulateHug()">模拟一次拥抱</button><button onclick="test('doll_set_led',{on:true})">点亮板载灯</button><button onclick="test('doll_set_led',{on:false})">关闭板载灯</button><pre id="result"></pre><p><a id="device" href="#" target="_blank">打开设备网页设置</a></p><p id="login"></p><small>此页的测试按钮通过 USB 调用设备工具。局域网 HTTP MCP 另行实测。</small></section><script>const csrf='__CSRF__';async function api(path,data){let r=await fetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:data?JSON.stringify(data):undefined});let d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d}async function refresh(){try{let d=await api('/status');document.querySelector('#status').textContent=d.wifi_connected?'✅ 已连接 '+d.ssid+'\nIP：'+d.ip+'\nMCP：http://'+d.ip+'/mcp':'尚未连接 Wi-Fi（状态 '+d.wifi_status+'），请完成配网。';document.querySelector('#device').href='http://'+(d.wifi_connected?d.ip:d.ap_ip)+'/'}catch(e){document.querySelector('#status').textContent=e.message}}async function scanWifi(){const b=document.querySelector('#scan'),list=document.querySelector('#networks'),hint=document.querySelector('#scanHint');b.disabled=true;hint.textContent='正在扫描，请稍候…';try{let d=await api('/scan',{start:true});for(let i=0;d.scanning&&i<25;i++){await new Promise(r=>setTimeout(r,800));d=await api('/scan',{start:false})}if(d.error)throw Error(d.error);if(d.scanning)throw Error('扫描超时，请重新扫描');list.replaceChildren(new Option('请选择网络，或手动输入隐藏网络',''));for(const n of d.networks){list.add(new Option(n.ssid+' · '+n.rssi+' dBm'+(n.secure?' · 需密码':' · 开放网络'),n.ssid))}hint.textContent=d.networks.length?'找到 '+d.networks.length+' 个网络，请选择后输入密码。':'未发现网络，可重新扫描或手动输入。'}catch(e){hint.textContent=e.message}finally{b.disabled=false}}async function join(){try{document.querySelector('#save').disabled=true;await api('/wifi',{ssid:document.querySelector('#ssid').value,password:document.querySelector('#password').value});document.querySelector('#password').value='';document.querySelector('#status').textContent='正在连接…'}catch(e){alert(e.message)}finally{document.querySelector('#save').disabled=false}}async function simulateHug(){try{const r=await api('/rpc',{jsonrpc:'2.0',id:2,method:'tools/call',params:{name:'get_channel_config',arguments:{}}});if(r.error||r.result?.isError)throw Error('无法读取通道配置');const data=r.result?.structuredContent||JSON.parse(r.result.content.find(x=>x.type==='text').text);const channels=data.channels||data.result?.channels||[];const ch=channels.find(c=>c.channel===3&&c.type==='pressure'&&c.enabled)||channels.find(c=>c.type==='pressure'&&c.enabled);if(!ch)throw Error('请先在互动页面添加并启用压力通道');await test('doll_simulate_press',{channel:ch.channel,value:3200})}catch(e){document.querySelector('#result').textContent=e.message}}async function test(name,args){try{let r=await api('/rpc',{jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});document.querySelector('#result').textContent=JSON.stringify(r,null,2)}catch(e){alert(e.message)}}(async()=>{let d=await api('/setup');document.querySelector('#login').textContent='设备网页账号：admin；密码：'+d.ap_password;await refresh();setInterval(refresh,4000)})();</script></html>'''.replace('__CSRF__',CSRF)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def allowed(self):
        return self.headers.get('Host') in ('127.0.0.1:8768','localhost:8768') and self.headers.get('Origin','') in ('','http://127.0.0.1:8768','http://localhost:8768')
    def authorized(self):
        return self.headers.get('X-CSRF-Token')==CSRF or (bool(COMPANION_TOKEN) and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+COMPANION_TOKEN))
    def event_stream(self,subscription_id):
        # fetch() uses auth headers; tokens never appear in URLs or event payloads.
        with COMPANION.lock:
            row=COMPANION.db.execute("SELECT id FROM bridge_subscriptions WHERE id=? AND owner='local-owner' AND active=1 AND transport='stream'",(subscription_id,)).fetchone()
        if not row:return self.send(404,{'error':'Inactive or unknown stream subscription'})
        # A refreshed window takes over its SAME target. The previous socket must
        # not claim a fresh event after its browser has gone away. Invalidate an
        # old stream lease; stable event IDs let model backends reuse its result.
        stream_id=secrets.token_hex(16)
        with STREAM_LOCK,COMPANION.lock,COMPANION.db:
            if subscription_id in STREAM_CLIENTS:
                COMPANION.db.execute("UPDATE bridge_outbox SET state='pending',lease=NULL WHERE subscription_id=? AND state='sending'",(subscription_id,))
            STREAM_CLIENTS[subscription_id]=stream_id
        self.connection.settimeout(5)
        try:
            self.send_response(200);self.send_header('Content-Type','text/event-stream; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.send_header('X-Accel-Buffering','no');self.end_headers()
            until=time.monotonic()+25
            while time.monotonic()<until and not COMPANION.stop.is_set():
                with STREAM_LOCK:
                    if STREAM_CLIENTS.get(subscription_id)!=stream_id:break
                    with COMPANION.lock:
                        active=COMPANION.db.execute('SELECT active,expires FROM bridge_subscriptions WHERE id=?',(subscription_id,)).fetchone()
                    if not active or not active['active'] or active['expires']<=time.time():break
                    delivery=COMPANION.bridge.claim('local-owner',subscription_id)
                if delivery:
                    public=dict(event=delivery['payload'],lease=delivery['lease'],subscription_id=subscription_id)
                    raw=('event: interaction\nid: '+delivery['event_id']+'\ndata: '+json.dumps(public,ensure_ascii=False)+'\n\n').encode()
                else:raw=b': heartbeat\n\n'
                self.wfile.write(raw);self.wfile.flush();COMPANION.stop.wait(.25 if delivery else 1)
        except (OSError,ConnectionError):pass
        finally:
            self.close_connection=True
            with STREAM_LOCK:
                if STREAM_CLIENTS.get(subscription_id)==stream_id:STREAM_CLIENTS.pop(subscription_id,None)
    def do_GET(self):
        parsed=urlsplit(self.path)
        if parsed.path=='/bridge/events':
            if not self.allowed() or not self.authorized():return self.send(403,{'error':'Forbidden'})
            values=parse_qs(parsed.query).get('subscription_id',[])
            if len(values)!=1:return self.send(400,{'error':'subscription_id required'})
            return self.event_stream(values[0])
        if self.path in ('/bridge-client.js','/bridge'):
            if not self.allowed():return self.send(403,{'error':'Forbidden'})
            asset='bridge_client.js' if self.path.endswith('.js') else 'bridge_demo.html'
            raw=(ROOT/'tools'/asset).read_text(encoding='utf-8').replace('__CSRF__',CSRF).encode()
            self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8' if asset.endswith('.js') else 'text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if self.path=='/bridge/status':
            if not self.allowed() or not self.authorized():return self.send(403,{'error':'Forbidden'})
            return self.send(200,COMPANION.bridge.state())
        if self.path=='/channel-editor.js':
            if not self.allowed():return self.send(403,{'error':'Forbidden'})
            data=(ROOT/'tools/channel_editor.js').read_bytes()
            self.send_response(200);self.send_header('Content-Type','application/javascript; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if not self.allowed():return self.send(403,{'error':'Forbidden host/origin'})
        if self.path=='/install-guide':
            raw=(Path(__file__).resolve().parents[1]/'docs/AI_INSTALL.md').read_bytes();self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if self.path=='/companion':
            raw=(Path(__file__).with_name('companion.html').read_text(encoding='utf-8').replace('__CSRF__',CSRF)).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if self.path=='/':
            raw=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        if self.headers.get('X-CSRF-Token')!=CSRF:return self.send(403,{'error':'Forbidden'})
        if self.path=='/companion/state':
            return self.send(200,{'active_session':COMPANION.active(),'collector_error':COMPANION.error,'last_sync':COMPANION.last_sync,'persona':COMPANION.setting('persona')})
        try:
            with LOCK:
                if self.path=='/status':r=exchange({'cmd':'status'})
                elif self.path=='/setup':r=exchange({'cmd':'setup'})
                else:return self.send(404,{'error':'Not found'})
            if self.path=='/status':(WORK/'latest-status.json').write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8')
            self.send(200,r)
        except Exception:return self.send(503,{'error':'设备串口暂时不可用，请关闭其他串口工具后重试。'})
    def do_POST(self):
        bearer=hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+COMPANION_TOKEN) if COMPANION_TOKEN else False
        csrf=self.headers.get('X-CSRF-Token')==CSRF
        if not self.allowed() or not (csrf or (bearer and (self.path=='/companion/tool' or self.path.startswith('/bridge/')))):return self.send(403,{'error':'Forbidden'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>16384:return self.send(413,{'error':'Request too large'})
            d=json.loads(self.rfile.read(length))
            if not isinstance(d,dict):return self.send(400,{'error':'Request must be an object'})
            if self.path=='/bridge/mcp':
                if not bearer:return self.send(401,{'error':'Bearer authentication required'})
                return self.send(200,EVENTS_ADAPTER.rpc(d,protocol_header=self.headers.get('MCP-Protocol-Version')))
            if self.path=='/bridge/subscriptions':
                return self.send(200,bridge_subscribe(d))
            if self.path in ('/bridge/unsubscribe','/bridge/ack','/bridge/renew'):
                method={'/bridge/unsubscribe':'unsubscribe','/bridge/ack':'acknowledge','/bridge/renew':'renew'}[self.path]
                allowed={'subscription_id'} if method=='unsubscribe' else {'subscription_id','event_id','lease'}|({'reply','source'} if method=='acknowledge' else set())
                if set(d)-allowed:raise ValueError('Unknown delivery fields')
                return self.send(200,getattr(COMPANION.bridge,method)('local-owner',**d))
            if self.path=='/bridge/preferences':
                return self.send(200,COMPANION.bridge.save_preferences(**d))
            if self.path=='/companion/tool':
                return self.send(200,COMPANION.call(d.get('name'),d.get('arguments',{})))
            if self.path=='/wifi':cmd={'cmd':'wifi','ssid':d.get('ssid'),'password':d.get('password')}
            elif self.path=='/scan':cmd={'cmd':'scan','start':d.get('start',False)}
            elif self.path=='/rpc':cmd={'cmd':'rpc','request':d}
            elif self.path=='/reboot':cmd={'cmd':'reboot'}
            else:return self.send(404,{'error':'Not found'})
            with LOCK:r=exchange(cmd)
            self.send(400 if r.get('error') else 200,r)
        except (ValueError,TypeError) as exc:return self.send(400,{'error':str(exc)})
        except Exception:
            traceback.print_exc()
            return self.send(503,{'error':'请求失败，请检查设备连接。'})

if __name__=='__main__':
    WORK.mkdir(parents=True,exist_ok=True)
    private=WORK/'companion-private.json'
    if not private.exists():private.write_text(json.dumps({'token':secrets.token_hex(32)}),encoding='utf-8')
    COMPANION_TOKEN=json.loads(private.read_text(encoding='utf-8'))['token']
    COMPANION=Companion(WORK/'interactions.sqlite3',exchange,LOCK)
    EVENTS_ADAPTER=MCPEventsAdapter(COMPANION,bridge_tools)
    bridge_tools()  # Build schemas once before requests can race initialization.
    server=ThreadingHTTPServer(('127.0.0.1',8768),Handler)
    threading.Thread(target=COMPANION.collect,daemon=True).start()
    threading.Thread(target=webhook_worker,args=(COMPANION.bridge,COMPANION.stop),daemon=True).start()
    print('USB setup: http://127.0.0.1:8768',flush=True)
    try:server.serve_forever()
    finally:COMPANION.stop.set();server.server_close();SERIAL_LINK.close()
