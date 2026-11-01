"""Current-board extension checks; temporary fixtures, no device access."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_companion_experience as context_fixtures
import test_interaction_bridge as bridge_fixtures
import companion_mcp

ROOT = Path(__file__).resolve().parents[1]


class NativeExpansionTests(unittest.TestCase):
    def test_actual_channel_parser_preserves_types_and_rejects_pin_conflicts(self):
        source=r'''
#include <string>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <iostream>
#include <assert.h>
class String:public std::string{public:using std::string::string;String(const std::string&s):std::string(s){}bool isEmpty()const{return empty();}size_t write(uint8_t c){push_back((char)c);return 1;}size_t write(const uint8_t*s,size_t n){append((const char*)s,n);return n;}};
#include <ArduinoJson.h>
namespace ArduinoJson {template<>struct Converter<String>{
 static String fromJson(JsonVariantConst v){return v.as<const char*>()?v.as<const char*>():"";}
 static bool checkJson(JsonVariantConst v){return v.is<const char*>();}
 static void toJson(const String&s,JsonVariant v){v.set(s.c_str());}
};}
static bool sensorEnabled=false;
#include "expansion_inputs.h"
#include "channel_devices.h"
bool accepts(const std::string&rows){JsonDocument a;assert(!deserializeJson(a,"{\"channels\":["+rows+"]}"));ChannelConfig next[MAX_CHANNELS];String error;return parseChannels(a.as<JsonVariantConst>(),next,error);}
int main(){
 std::string head=R"({"channel":0,"name":"head","type":"pressure","driver":"mux_adc","mux_port":0,"mode":"connected","options":{"press_threshold":699,"release_threshold":295}})";
 std::string contact=R"({"channel":13,"name":"contact","type":"switch","driver":"gpio_switch","gpio":21,"mode":"off","options":{"debounce_ms":40}})";
 assert(accepts(head+","+contact));assert(!accepts(head+","+head));
 for(const char* kind:{"temperature","motion","vibration","light"})assert(!accepts(std::string("{\"channel\":8,\"name\":\"removed\",\"type\":\"")+kind+"\",\"driver\":\"simulation\"}"));
 assert(!accepts(R"({"channel":0,"name":"wrong","type":"switch","driver":"gpio_switch","gpio":20})"));
 JsonDocument saved;deserializeJson(saved,"{\"channels\":["+head+","+contact+R"(,{"channel":8,"name":"probe","type":"temperature","driver":"ds18b20","gpio":1,"rom":"savedROM"},{"channel":11,"name":"motor","type":"vibration","driver":"gpio_pwm","gpio":10}]})");
 retireUnsupportedChannels(saved);assert(saved["channels"].size()==2&&retiredChannelCount==2);
 ChannelConfig next[MAX_CHANNELS];String error;assert(parseChannels(saved.as<JsonVariantConst>(),next,error));assert(next[0].on==699&&next[0].off==295&&next[0].name=="head"&&next[13].gpio==21);
 JsonDocument retired;assert(!deserializeJson(retired,retiredChannels));assert(retired[0]["rom"]=="savedROM"&&retired[1]["gpio"]==10);
 JsonDocument persisted;encodeChannels(persisted.to<JsonObject>(),next);persisted["retired_channels"]=serialized(retiredChannels);persisted["resume_inputs"]=true;
 std::string savedBlob;serializeJson(persisted,savedBlob);retiredChannels="[]";deserializeJson(persisted,savedBlob);retireUnsupportedChannels(persisted);assert(retiredChannelCount==2&&persisted["channels"].size()==2); // Reboot never duplicates or activates retired rows.
 JsonDocument caps;channelCapabilities(caps.to<JsonObject>());assert(caps["types"].size()==2&&caps["physical_outputs_supported"]==false);
}
'''
        with tempfile.TemporaryDirectory(prefix='aidoll-config-') as folder:
            program=Path(folder)/'test.cpp';program.write_text(source,encoding='utf-8')
            binary=Path(folder)/'test.exe'
            includes=[ROOT/'firmware/src',ROOT/'firmware/.pio/libdeps/supermini-lab/ArduinoJson/src']
            result=subprocess.run([shutil.which('g++') or 'g++','-std=c++11',*[arg for p in includes for arg in ('-I',str(p))],str(program),'-o',str(binary)],capture_output=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace')[-5000:])
            result=subprocess.run([str(binary)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

    def test_debounce_motion_motor_suppression_and_light(self):
        source = r'''
#include <assert.h>
#include "expansion_inputs.h"
int main(){
 ContactInput s;
 assert(!s.sample(true,100,40)); // Held at boot is baseline, not a new close.
 assert(!s.sample(false,110,40)); assert(!s.sample(true,120,40));
 assert(!s.sample(false,130,40)); assert(!s.sample(false,169,40));
 assert(s.sample(false,170,40)&&!s.active);
 assert(!s.sample(true,180,40)); assert(s.sample(true,220,40)&&s.active);

}
'''
        with tempfile.TemporaryDirectory(prefix='aidoll-inputs-') as folder:
            program=Path(folder)/'test.cpp';program.write_text(source,encoding='utf-8')
            binary=Path(folder)/'test.exe'
            subprocess.run([shutil.which('g++') or 'g++','-std=c++11','-I',str(ROOT/'firmware/src'),str(program),'-o',str(binary)],check=True,capture_output=True,timeout=40)
            result=subprocess.run([str(binary)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))


class ContextExpansionTests(unittest.TestCase):
    setUp=context_fixtures.ExperienceTests.setUp
    tearDown=context_fixtures.ExperienceTests.tearDown
    save_config=context_fixtures.ExperienceTests.save_config
    config=context_fixtures.ExperienceTests.config
    device=context_fixtures.ExperienceTests.device
    event=context_fixtures.ExperienceTests.event
    def test_temperature_threshold_and_acknowledged_baseline(self):
        e=self.c.experience;e.update_preferences({'policy':{'temperature_enabled':True,'cooldown_ms':0}})
        for seq,value in enumerate([25,25.4,26.2],1):
            self.event(seq,age=3-seq,sensor_type='temperature',phase='sample',touch_id=None,event_id='temp-'+str(seq),unit='degC',value=value)
        first=e.context('temperature-chat');self.assertEqual([v['value'] for v in first['events']],[26.2])
        self.assertEqual(first['receipt_id'],e.context('temperature-chat')['receipt_id'])
        e.acknowledge('temperature-chat',first['receipt_id'])
        self.assertFalse(e.context('temperature-chat')['events'])
        self.event(4,sensor_type='temperature',phase='sample',touch_id=None,event_id='temp-4',unit='degC',value=26.4)
        self.assertFalse(e.context('temperature-chat')['events'])
    def test_motion_switch_opt_in_receipts_and_chat_isolation(self):
        e=self.c.experience
        self.event(1,sensor_type='motion',phase='shake',touch_id=None,event_id='motion-1',unit='g',value=2)
        self.event(2,age=1,sensor_type='switch',phase='close',touch_id=None,event_id='switch-1',unit='boolean',value=1)
        self.event(3,sensor_type='switch',phase='open',touch_id=None,event_id='switch-2',unit='boolean',value=0)
        self.event(4,sensor_type='light',phase='output',direction='output',touch_id=None)
        self.event(5,sensor_type='motion',phase='sample',touch_id=None)
        self.assertFalse(e.context('chat-a')['events'])
        e.update_preferences({'policy':{'motion_enabled':True,'switch_enabled':True,'cooldown_ms':0}})
        a=e.context('chat-a');self.assertEqual([v['sensor_type'] for v in a['events']],['motion','switch'])
        self.assertEqual(e.context('chat-a')['receipt_id'],a['receipt_id'])
        e.acknowledge('chat-a',a['receipt_id']);self.assertFalse(e.context('chat-a')['events'])
        self.assertEqual(len(e.context('chat-b')['events']),2)
        self.assertTrue(e.acknowledge('chat-a',a['receipt_id'])['duplicate'])


class BridgeExpansionTests(unittest.TestCase):
    setUp=bridge_fixtures.BridgeTests.setUp
    tearDown=bridge_fixtures.BridgeTests.tearDown
    subscribe=bridge_fixtures.BridgeTests.subscribe
    event=bridge_fixtures.BridgeTests.event
    count=bridge_fixtures.BridgeTests.count
    claim=bridge_fixtures.BridgeTests.claim
    def test_optional_motion_switch_and_no_output_loop(self):
        sub=self.subscribe(policy=dict(motion_enabled=True,switch_enabled=True,merge_ms=0,cooldown_ms=0))
        self.event(kind='motion',phase='sample');self.event(.2,kind='switch',phase='open')
        self.event(.3,kind='light',phase='output');self.assertEqual(self.count(),0)
        self.event(.4,kind='motion',phase='shake');self.event(.5,kind='switch',phase='close')
        self.assertEqual(self.count(),2)
        item=self.claim(sub);self.assertEqual(item['payload']['data']['events'][0]['sensor_type'],'motion')

    def test_user_actions_extend_idle_but_periodic_and_output_events_do_not(self):
        self.subscribe()
        def emit(seq,kind,phase):
            event=dict(seq=seq,uptime_ms=seq*1000,channel=0,phase=phase,sensor_type=kind,direction='output' if kind=='light' else 'input',source='sensor',quality='ok',delivery_quality='live',value=1,body_part='test')
            with self.c.lock,self.c.db:self.c.archive_event('doll','boot',event,self.now+seq,self.now+seq)
        emit(2,'motion','shake')
        before=self.c.db.execute('SELECT last_activity FROM sessions WHERE id=?',('s',)).fetchone()[0]
        self.assertEqual(before,self.now+2)
        emit(3,'temperature','sample')
        emit(4,'light','output')
        self.assertEqual(self.c.db.execute('SELECT last_activity FROM sessions WHERE id=?',('s',)).fetchone()[0],before)


class ExpansionMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_light_write_schema_and_full_config_preservation(self):
        with patch.object(companion_mcp,'call',return_value={}) as forwarded:
            await companion_mcp.mcp.call_tool('set_light',dict(channel=12,brightness=20,pattern='breathe',duration_ms=2000))
            self.assertEqual(forwarded.call_args.args[0],'set_light')
            channels=[dict(channel=0,name='头',type='pressure',driver='mux_adc',mux_port=0,options={'press_threshold':699,'release_threshold':295}),
                      dict(channel=10,name='动作',type='motion',driver='lis3dh',address=24,mode='off',options={})]
            await companion_mcp.mcp.call_tool('set_channel_config',dict(channels=channels))
            self.assertEqual(forwarded.call_args.args[1]['channels'],channels)
        with patch.object(companion_mcp,'call') as forwarded:
            for args in [dict(channel=12,brightness=101),dict(channel=12,brightness=20,pattern='rgb'),dict(channel=12,brightness=20,duration_ms=-1)]:
                with self.assertRaises(Exception):await companion_mcp.mcp.call_tool('set_light',args)
            forwarded.assert_not_called()
        light=next(t for t in await companion_mcp.mcp.list_tools() if t.name=='set_light')
        self.assertFalse(light.annotations.readOnlyHint)


if __name__=='__main__':unittest.main()
