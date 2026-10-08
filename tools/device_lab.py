"""Serial setup and real-device HTTP MCP smoke test. Secrets stay in ignored build/."""
import argparse, base64, json, pathlib, sys, time, urllib.request, urllib.error, secrets
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools/python-packages'))
import serial
WORK=ROOT/'build/device-lab'
CONFIG=WORK/'device-private.json'

class SerialLink:
    """Keep CDC open for the collector; callers serialize requests with one lock."""
    def __init__(self,port='COM3'):
        self.port=port;self.connection=None
        self.require_request_id=False

    def close(self):
        if self.connection is not None:
            self.connection.close();self.connection=None

    def exchange(self,command,timeout=8):
        try:
            return self._exchange_once(command,timeout)
        except (TimeoutError,serial.SerialException):
            # A disconnected CDC link can recover on the next open. Retry only
            # immutable reads; never repeat an ACK, output, reboot or setting.
            if command.get('cmd') not in ('status','events'):
                raise
            time.sleep(.5)
            return self._exchange_once(command,timeout)

    def _exchange_once(self,command,timeout=8):
        try:
            if self.connection is None:
                s=serial.Serial(port=None,baudrate=115200,timeout=.3)
                s.dtr=False;s.rts=False;s.port=self.port;s.open()
                self.connection=s;time.sleep(.5)
            s=self.connection;s.reset_input_buffer()
            ident=secrets.token_hex(12)
            line=json.dumps(dict(command,serial_request_id=ident),ensure_ascii=True)
            if (len(line)+1)%64==0:line+=' '
            wire=(line+'\n').encode()
            for offset in range(0,len(wire),64):
                s.write(wire[offset:offset+64]);s.flush();time.sleep(.004)
            end=time.monotonic()+timeout
            pending=b'';received=0;frames=[]
            while time.monotonic()<end:
                chunk=s.read(max(1,s.in_waiting));received+=len(chunk);pending+=chunk
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1);frames.append(len(line))
                    try:r=json.loads(line)
                    except (ValueError,UnicodeDecodeError):continue
                    if not isinstance(r,dict) or 'event' in r:continue
                    echo=r.get('serial_request_id')
                    if echo==ident:
                        self.require_request_id=True
                        r.pop('serial_request_id',None)
                        return r
                    if echo is not None or self.require_request_id:continue
                    return r  # Compatibility with old firmware without echo support.
            raise TimeoutError('No serial JSON reply; bytes='+str(received)+' frames='+str(frames))
        except Exception:
            self.close();raise

def exchange(command,port='COM3',timeout=6):
    connection=serial.Serial(port=None,baudrate=115200,timeout=.3)
    connection.dtr=False;connection.rts=False;connection.port=port
    with connection as s:
        time.sleep(.5);s.reset_input_buffer()
        s.write((json.dumps(command,ensure_ascii=True)+'\n').encode());s.flush()
        end=time.time()+timeout
        while time.time()<end:
            line=s.readline()
            try:r=json.loads(line)
            except (ValueError,UnicodeDecodeError):continue
            if 'event' not in r:return r
    raise TimeoutError('No serial JSON reply')

def capture(port):
    setup=exchange({'cmd':'setup'},port)
    state=exchange({'cmd':'status'},port)
    assert 'mcp_token' in setup and state['firmware'].startswith('doll-lab-')
    setup['port']=port;setup['state']=state
    CONFIG.write_text(json.dumps(setup,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(state,ensure_ascii=False,indent=2))
    print('Private connection settings saved locally (not printed).')

def test(host):
    cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    records=[]
    def request(payload=None,path='/mcp',auth=True,admin=False,method=None):
        headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json','MCP-Protocol-Version':'2025-11-25'}
        if auth:headers['Authorization']='Bearer '+cfg['mcp_token']
        if admin:
            headers['Authorization']='Basic '+base64.b64encode(('admin:'+cfg['ap_password']).encode()).decode()
            headers['X-Setup-Token']=cfg['mcp_token']
        req=urllib.request.Request('http://'+host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers,method=method)
        try:
            with opener.open(req,timeout=10) as response:
                raw=response.read();return response.status,json.loads(raw) if raw else None
        except urllib.error.HTTPError as ex:return ex.code,ex.read().decode()
    def rpc(method,params=None):
        ident=len(records)+1
        status,r=request(dict(jsonrpc='2.0',id=ident,method=method,params=params or {}))
        assert status==200 and r.get('id')==ident,(status,r)
        records.append(dict(method=method,params=params,response=r))
        return r
    assert request(dict(jsonrpc='2.0',id=1,method='ping'),auth=False)[0]==401
    assert request(method='GET')[0]==405
    r=rpc('initialize',dict(protocolVersion='2025-11-25',capabilities={},clientInfo=dict(name='doll-real-device-test',version='1.0')))
    assert r['result']['protocolVersion']=='2025-11-25'
    assert request(dict(jsonrpc='2.0',method='notifications/initialized'))[0]==202
    r=rpc('tools/list');assert {'doll_get_status','doll_set_led','doll_simulate_press'}.issubset({t['name'] for t in r['result']['tools']})
    def call(name,args):return rpc('tools/call',dict(name=name,arguments=args))
    def data(r):return json.loads(r['result']['content'][0]['text'])
    assert data(call('doll_set_led',{'on':True}))['led_on'] is True
    assert data(call('doll_set_led',{'on':False}))['led_on'] is False
    r=data(call('doll_simulate_press',{'channel':3,'value':3200}));assert r['pressed_channel']==3 and r['sensor_mode']=='simulation';print('Device reaction:',r['reaction'])
    assert call('doll_simulate_press',{'channel':8,'value':500})['error']['code']==-32602
    time.sleep(5.2)
    r=data(call('doll_get_status',{}));assert r['pressed_channel']==-1 and r['pressure']==0
    assert request({'enabled':False},'/api/mcp',admin=True)[0]==200
    assert request(dict(jsonrpc='2.0',id=100,method='ping'))[0]==503
    assert request({'enabled':True},'/api/mcp',admin=True)[0]==200
    assert rpc('ping')['result']=={}
    report=dict(host=host,passed=True,tests=['unauthorized=401','GET=405','initialize','notification=202','tools/list','LED on/off','simulate press','invalid channel rejected','auto release','MCP disable/enable'],exchanges=records)
    (WORK/('mcp-test-'+host.replace('.','_')+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS:',', '.join(report['tests']))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['capture','test','status']);p.add_argument('--port',default='COM3');p.add_argument('--host',default='192.168.4.1');a=p.parse_args();WORK.mkdir(exist_ok=True,parents=True)
    if a.action=='capture':capture(a.port)
    elif a.action=='test':test(a.host)
    else:print(json.dumps(exchange({'cmd':'status'},a.port),ensure_ascii=False,indent=2))
