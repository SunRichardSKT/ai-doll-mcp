"""Owner-triggered local pairing of a LAN doll; credentials are never returned."""
import base64
import ipaddress
import json
from pathlib import Path
import urllib.error
import urllib.request

from private_storage import write_json


def configure_device(app, data):
    if not isinstance(data.get('username', ''), str) or not isinstance(data.get('password', ''), str):
        raise ValueError('设备账号和密码必须是文本。')
    try:
        ip = ipaddress.ip_address(data.get('host','').strip())
        if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            raise ValueError()
    except (ValueError,AttributeError):
        raise ValueError('请填写设备的局域网 IPv4 地址，例如 192.168.1.50。') from None
    if not app.public_url:
        raise ValueError('请先设置设备能访问的服务器地址。')
    headers={'Content-Type':'application/json'}
    if data.get('password'):
        user=data.get('username') or 'admin'
        headers['Authorization']='Basic '+base64.b64encode((user+':'+data['password']).encode()).decode()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path,body=None):
        request=urllib.request.Request('http://'+str(ip)+path,headers=headers,
            data=None if body is None else json.dumps(body).encode())
        try:
            with opener.open(request,timeout=5) as response:return json.load(response)
        except urllib.error.HTTPError as e:
            code=e.code;e.read();e.close()
            if code==401:raise ValueError('设备已开启登录保护，请填写该设备的账号密码。') from None
            raise ValueError('设备拒绝配置，请检查设备固件和配网状态。') from None
        except (OSError,ValueError):
            raise ValueError('暂时无法读取设备。请确认设备已配网、电脑在同一局域网，然后重试。') from None
    setup=call('/api/setup');state=call('/api/status')
    hardware=state.get('device_id','')
    if not isinstance(hardware,str) or not hardware.startswith('AI-Doll-') or not str(state.get('firmware','')).startswith('doll-lab-') or not state.get('wifi_connected'):
        raise ValueError('未识别到已联网的 AI Doll，请先给开发板配网。')
    token=setup.get('token','')
    if not isinstance(token,str) or len(token)<16:raise ValueError('设备设置接口不完整，请更新固件。')
    headers['X-Setup-Token']=token
    path=app.folder/'auto-pairing-private.json'
    with app.lock:
        saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        record=saved.get(hardware)
        if record:
            try:app.resolve(record['id'])
            except ValueError:record=None
        if not record:
            record=app.pair(data.get('label') or '我的娃娃')
            with app.db:app.db.execute('UPDATE devices SET hardware_id=? WHERE id=?',(hardware,record['id']))
            saved[hardware]=record;write_json(path,saved)
    result=call('/api/uplink',dict(enabled=True,server_url=app.public_url,
        device_token=record['device_token'],local_http=app.public_url.startswith('http://'),root_ca=''))
    if not result.get('ok'):raise ValueError('设备未确认保存，请在设备设置页检查直连配置。')
    return dict(configured=True,id=record['id'],hardware_id=hardware,waiting_for_upload=True)
