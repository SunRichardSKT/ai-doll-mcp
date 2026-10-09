"""Bare-board regression: no ADC sampling, motor arming or claimed physical calibration."""
import asyncio, datetime, json, pathlib, site, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
SDK=ROOT/'.tools/mcp-test-sdk'
if SDK.exists():sys.path.insert(0,str(SDK));site.addsitedir(str(SDK))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
 checks=[]
 async with stdio_client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'tools/companion_mcp.py')])) as (r,w):
  async with ClientSession(r,w) as session:
   await session.initialize();names={t.name for t in (await session.list_tools()).tools}
   expected={'get_operating_mode','set_operating_mode','capture_pressure_calibration','get_pressure_calibration','apply_pressure_calibration','cancel_pressure_calibration'}
   assert len(names)==45 and expected<=names
   async def call(name,args=None,error=False):
    result=await session.call_tool(name,args or {})
    if error:assert result.isError,(name,result);return
    assert not result.isError,(name,result);return json.loads(result.content[0].text)
   status=await call('doll_get_status');assert status['firmware']=='doll-lab-2.7.0'
   assert not (await call('get_interaction_status'))['active_session'],'Do not interrupt a user session'
   mode=await call('get_operating_mode');assert mode['mode']=='manual' and not mode['physical_inputs_enabled'] and not mode['physical_outputs_enabled']
   original=await call('get_channel_config')
   await call('set_operating_mode',{'mode':'daily','hardware_confirmed':False},error=True)
   assert (await call('get_operating_mode'))==mode
   await call('capture_pressure_calibration',{'channel':0,'stage':0},error=True)
   await call('apply_pressure_calibration',error=True)
   assert (await call('get_channel_config'))==original
   checks.append('45 tools; boot manual; daily mode without hardware confirmation rejected; disabled sampling cannot calibrate/save')
   await call('cancel_pressure_calibration');assert not (await call('get_pressure_calibration'))['engaged']
   await call('simulate_channel_input',{'channel':0,'value':1700})
   value=next(v for v in (await call('read_channel_values'))['values'] if v['channel']==0)
   assert value['active'] and value['source']=='simulation' and value['quality']=='ok' and value['press_threshold']>value['release_threshold']
   await call('simulate_channel_input',{'channel':0,'value':0})
   value=next(v for v in (await call('read_channel_values'))['values'] if v['channel']==0)
   assert not value['active'] and value['value']==0
   assert (await call('get_channel_config'))==original
   checks.append('diagnostics expose active state, per-channel thresholds and explicit simulation source without overwriting config')
   result=await call('set_operating_mode',{'mode':'manual'})
   assert not result['resume_inputs_after_reboot'] and not result['outputs_resume_after_reboot']
   checks.append('manual startup saved atomically; outputs remain disarmed')
 report=dict(passed=True,firmware='doll-lab-2.7.0',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,
             not_tested=['physical pressure calibration','daily-mode physical input resume','real motor/temperature'])
 (ROOT/'build/device-lab/sensor-experience-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');asyncio.run(main())
