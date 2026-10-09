"""Bare-board digital configuration/absence test. No physical inputs or outputs enabled."""
import asyncio
import datetime
import json
import os
import pathlib
import site
import sys
import copy
ROOT=pathlib.Path(__file__).resolve().parents[1];WORK=ROOT/'build/device-lab';SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

def rom_address(serial):
    address=bytearray([0x28,serial,2,3,4,5,6]);crc=0
    for byte in address:
        for _ in range(8):
            mix=(crc^byte)&1;crc>>=1
            if mix:crc^=0x8c
            byte>>=1
    address.append(crc)
    return address.hex()

async def main():
    port=os.environ.get('DOLL_TEST_REBOOT_PORT')
    if not port:raise ValueError('Set DOLL_TEST_REBOOT_PORT for the explicitly authorized maintenance reboot')
    checks=[]
    async with stdio_client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])) as (r,w):
      async with ClientSession(r,w) as session:
        await session.initialize();tools=(await session.list_tools()).tools
        assert len(tools)==45 and next(t for t in tools if t.name=='scan_input_devices').annotations.readOnlyHint
        async def call(name,args=None,error=False):
            result=await session.call_tool(name,args or {})
            if error:
                assert result.isError,(name,result);return
            assert not result.isError,(name,result)
            return json.loads(result.content[0].text)
        status=await call('doll_get_status');original=await call('get_channel_config');mode=await call('get_operating_mode')
        assert status['firmware']=='doll-lab-2.7.0' and status['sensor_mode']=='simulation'
        assert mode['mode']=='manual' and not mode['physical_outputs_enabled']
        assert not (await call('get_interaction_status'))['active_session']
        caps=await call('get_channel_capabilities')
        assert 'ds18b20' in next(t for t in caps['types'] if t['type']=='temperature')['drivers']
        empty=await call('scan_input_devices')
        assert empty['devices']==[] and empty['quality']=='no_device_found' and not empty['physical_sampling_enabled']
        assert await call('get_channel_config')==original
        checks.append('45 MCP tools; digital capability; bare GPIO1 scan reports no probe without enabling inputs')
        assert len(original['channels'])==8,'Run against the authorized eight-channel standalone test board only'
        expanded=copy.deepcopy(original['channels'])
        expanded.extend(dict(channel=8+i,name='数字温度测试'+str(i),type='temperature',driver='ds18b20',gpio=1,rom=rom_address(i),options={}) for i in range(2))
        try:
            saved=await call('set_channel_config',{'channels':expanded})
            assert saved['channels'][:8]==original['channels']
            assert [c['rom'] for c in saved['channels'][8:]]==[rom_address(0),rom_address(1)]
            assert all(c['options']['model']=='ds18b20' for c in saved['channels'][8:])
            checks.append('Two distinct CRC-valid ROMs share GPIO1; original pressure parameters preserved')
            invalid=[]
            for change in ({'rom':'28'+'00'*7},{'gpio':8},{'type':'pressure'},
                           {'options':{'model':'ntc_b3950'}},{'options':{'r0_ohm':10000}},
                           {'options':{'sample_ms':500}}, {'rom':rom_address(0)}):
                case=copy.deepcopy(saved['channels']);case[-1].update(change);invalid.append(case)
            for order in (False,True):
                adc=dict(channel=10,name='冲突ADC',type='temperature',driver='gpio_adc',gpio=1,options={})
                case=copy.deepcopy(saved['channels']);case.insert(0 if order else len(case),adc);invalid.append(case)
            for case in invalid:await call('set_channel_config',{'channels':case},error=True)
            assert await call('get_channel_config')==saved
            checks.append('Duplicate ROM, CRC, wrong pin/type/model/options and ADC bus conflicts rejected atomically in either order')
            await call('simulate_channel_input',{'channel':8,'value':-55,'unit':'degC'})
            await call('simulate_channel_input',{'channel':8,'value':-55.1,'unit':'degC'},error=True)
            await call('simulate_channel_input',{'channel':8,'value':1336,'unit':'millivolt'},error=True)
            await call('simulate_channel_input',{'channel':9,'value':32.5,'unit':'degC'})
            values=(await call('read_channel_values'))['values']
            for ch,expected in ((8,-55),(9,32.5)):
                value=next(v for v in values if v['channel']==ch)
                assert value['value']==expected and value['source']=='simulation' and value['adc_mv'] is None
            history=await call('query_device_history',{'sensor_type':'temperature','body_part':'数字温度测试1'})
            assert any(e['driver']=='ds18b20' and e['source']=='simulation' and e['value']==32.5 for e in history['events'])
            checks.append('Digital Celsius model range and mixed archive work; millivolt conversion rejected; simulation source preserved')
            from device_lab import SerialLink
            link=SerialLink(port)
            try:assert link.exchange({'cmd':'reboot'})['ok']
            finally:link.close()
            current=None
            for _ in range(40):
                await asyncio.sleep(.5)
                try:current=await call('doll_get_status')
                except AssertionError:continue
                if current['boot_id']!=status['boot_id']:break
            assert current['boot_id']!=status['boot_id']
            assert await call('get_channel_config')==saved
            assert not current['physical_outputs_enabled'] and current['sensor_mode']=='simulation'
            checks.append('Digital ROM bindings survive maintenance reboot; inputs and outputs remain disabled')
        finally:
            await call('set_channel_config',{'channels':original['channels']})
        assert await call('get_channel_config')==original
        assert await call('get_operating_mode')==mode
        checks.append('Original eight channels and manual mode restored')
    report=dict(passed=True,at=datetime.datetime.now().astimezone().isoformat(),firmware='2.7.0',checks=checks,
                not_tested=['Actual DS18B20 temperature, electrical timing and multi-probe wiring','Physical NTC/FSR/motor'])
    (WORK/'digital-device-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
