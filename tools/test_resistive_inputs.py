"""Production NTC/wet-pad logic and host archive/context behavior; no USB writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import test_companion_experience as fixtures
import test_interaction_bridge as bridge_fixtures

ROOT = Path(__file__).resolve().parents[1]


class ResistiveNativeTests(unittest.TestCase):
    def test_temperature_conversion_and_wet_episode_timing(self):
        source = r'''
#include <cassert>
#include "resistive_inputs.h"
int main(){
 NtcOptions o;float c=0;
 assert(o.r25==10000&&o.beta==3950);
 assert(ntcTemperature(289.959f,o,c)&&fabsf(c+19)<.02);
 assert(ntcTemperature(682.939f,o,c)&&fabsf(c)<.02);
 assert(ntcTemperature(1336.0324f,o,c)&&fabsf(c-25)<.02);
 assert(ntcTemperature(1575.833f,o,c)&&fabsf(c-36)<.02);
 assert(ntcTemperature(1649.879f,o,c)&&fabsf(c-40)<.02);
 assert(ntcTemperature(2061.042f,o,c)&&fabsf(c-79)<.02);
 assert(!ntcTemperature(240,o,c)&&!ntcTemperature(2100,o,c));
 assert(!ntcTemperature(0,o,c)&&!ntcTemperature(3300,o,c));
 assert(!ntcTemperature(2244.898f,o,c)); // Shorted probe, 4.7k/10k divider ceiling.
 assert(!ntcTemperature(NAN,o,c));
 o.offset=1;assert(ntcTemperature(1336.0324f,o,c)&&fabsf(c-26)<.02);
 TemperatureInput t;
 assert(t.sample(25,0,o));assert(!t.sample(25.4,1000,o));
 assert(t.sample(26,2000,o));assert(!t.sample(26.2,31000,o));assert(t.sample(26.2,32000,o));
 WetInput w;WetOptions p;
 assert(!w.sample(0,500,250,true,0,p));
 assert(!w.sample(1000,500,250,true,1,p));assert(!w.sample(1000,500,250,true,600,p));
 assert(w.sample(1000,500,250,false,601,p)==1); // Confirm wet without any pressure reply.
 assert(w.sample(1000,500,250,true,620,p)==2); // Pressure may arrive after wet confirmation.
 for(int i=0;i<5;i++)assert(!w.sample(1000,500,250,i%2,700+i*100,p));
 assert(!w.sample(0,500,250,true,1500,p));assert(!w.sample(1000,500,250,true,2000,p));
 assert(!w.sample(0,500,250,false,2100,p));assert(!w.sample(0,500,250,false,3099,p));
 assert(w.sample(0,500,250,false,3100,p)==4);
 assert(!w.sample(1000,500,250,true,3200,p));assert(w.sample(1000,500,250,true,3800,p)==3);
 WetInput noise;
 assert(!noise.sample(1000,500,250,true,0,p));assert(!noise.sample(300,500,250,true,599,p));
 assert(!noise.sample(1000,500,250,true,600,p));assert(!noise.sample(1000,500,250,true,1199,p));
 assert(noise.sample(1000,500,250,true,1200,p)==3);
}
'''
        with tempfile.TemporaryDirectory(prefix='aidoll-resistive-') as folder:
            work=Path(folder);program=work/'test.cpp';binary=work/'test.exe'
            program.write_text(source,encoding='utf-8')
            compiled=subprocess.run([shutil.which('g++') or 'g++','-std=c++11','-I',str(ROOT/'firmware/src'),str(program),'-o',str(binary)],capture_output=True,timeout=40)
            self.assertEqual(compiled.returncode,0,compiled.stderr.decode(errors='replace'))
            ran=subprocess.run([str(binary)],capture_output=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr.decode(errors='replace'))


class WetContextTests(unittest.TestCase):
    setUp=fixtures.ExperienceTests.setUp
    tearDown=fixtures.ExperienceTests.tearDown
    save_config=fixtures.ExperienceTests.save_config
    config=fixtures.ExperienceTests.config
    device=fixtures.ExperienceTests.device
    event=fixtures.ExperienceTests.event

    def test_only_opted_in_wipe_gets_one_chat_receipt(self):
        for seq,phase in enumerate(['wet','wipe','dry'],1):
            self.event(seq,sensor_type='wetness',phase=phase,touch_id=None,event_id='wet-'+str(seq),unit='boolean',value=int(phase!='dry'))
        e=self.c.experience
        self.assertFalse(e.context('chat-a')['events'])
        e.update_preferences({'policy':{'wetness_enabled':True,'cooldown_ms':0}})
        a=e.context('chat-a');self.assertEqual([x['phase'] for x in a['events']],['wipe'])
        self.assertEqual(a['receipt_id'],e.context('chat-a')['receipt_id'])
        e.acknowledge('chat-a',a['receipt_id']);self.assertFalse(e.context('chat-a')['events'])
        self.assertEqual(len(e.context('chat-b')['events']),1)
        # Reading again or a missed release never turns wet/dry into extra main feedback.
        self.assertEqual(self.c.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],3)

    def test_new_temperature_baseline_supersedes_old_acknowledgement(self):
        e=self.c.experience;e.update_preferences({'policy':{'temperature_enabled':True,'cooldown_ms':0}})
        for seq,value in enumerate([25,26.2],1):
            self.event(seq,age=6-seq,sensor_type='temperature',phase='sample',touch_id=None,value=value,unit='degC')
        first=e.context('temperature-chat');e.acknowledge('temperature-chat',first['receipt_id'])
        self.event(3,age=3,sensor_type='temperature',phase='baseline',touch_id=None,value=35,unit='degC')
        self.event(4,age=2,sensor_type='temperature',phase='sample',touch_id=None,value=35.3,unit='degC')
        self.assertFalse(e.context('temperature-chat')['events'])
        self.event(5,age=1,sensor_type='temperature',phase='sample',touch_id=None,value=36.2,unit='degC')
        self.assertEqual([x['value'] for x in e.context('temperature-chat')['events']],[36.2])

    def test_wipe_is_not_discarded_by_previous_pressure_cooldown(self):
        e=self.c.experience;e.update_preferences({'policy':{'wetness_enabled':True}})
        self.event(1,age=1)
        first=e.context('chat-a');e.acknowledge('chat-a',first['receipt_id'])
        self.event(2,age=.4,sensor_type='wetness',phase='wipe',touch_id=None,event_id='wet-2',unit='boolean',value=1)
        self.assertEqual([x['phase'] for x in e.context('chat-a')['events']],['wipe'])


class WetBridgeTests(unittest.TestCase):
    setUp=bridge_fixtures.BridgeTests.setUp
    tearDown=bridge_fixtures.BridgeTests.tearDown
    subscribe=bridge_fixtures.BridgeTests.subscribe
    event=bridge_fixtures.BridgeTests.event
    count=bridge_fixtures.BridgeTests.count

    def test_reboot_temperature_baseline_cannot_wake_chat(self):
        self.subscribe(policy={'temperature_enabled':True,'merge_ms':0,'cooldown_ms':0})
        self.event(.1,kind='temperature',phase='baseline',value=25)
        self.event(.2,kind='temperature',phase='sample',value=26.2)
        self.assertEqual(self.count(),1)
        self.event(.3,kind='temperature',phase='baseline',value=35)
        self.event(.4,kind='temperature',phase='sample',value=35.3)
        self.assertEqual(self.count(),1)
        self.event(.5,kind='temperature',phase='sample',value=36.2)
        self.assertEqual(self.count(),2)

    def test_wipe_waits_instead_of_disappearing_in_pressure_cooldown(self):
        self.subscribe(policy={'wetness_enabled':True})
        self.event(.1)
        self.event(.4,kind='wetness',phase='wet',value=1)
        self.event(.7,kind='wetness',phase='wipe',value=1)
        self.event(.9,kind='wetness',phase='dry',value=0)
        self.assertEqual(self.count(),2)
        rows=self.c.db.execute('SELECT payload FROM bridge_outbox ORDER BY id').fetchall()
        import json
        self.assertEqual(json.loads(rows[1]['payload'])['data']['events'][0]['phase'],'wipe')


if __name__=='__main__':unittest.main()
