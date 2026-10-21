"""Presentation and cursor checks use isolated fixtures, never an owner's device."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from companion import Companion


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'history.sqlite3'
        self.c = Companion(self.path, None, threading.Lock())
        self.now = time.time()
        self.channels = [dict(channel=i,name='头' if i==0 else '手',type='pressure',driver='mux_adc',enabled=True,
                              mux_port=i,options={'press_threshold':1200,'release_threshold':800}) for i in range(2)]
        self.calls=[]
        self.port_states=False
        self.save_config()
        self.c.set_setting('collector_last_device','fixture')
        self.c.device=self.device

    def save_config(self):
        self.c.set_setting('cached_get_channel_config',json.dumps({'data':self.config(),'saved_at':self.now}))

    def config(self):
        data={'channels':json.loads(json.dumps(self.channels))}
        if self.port_states:data['port_state_model']='per_port_v1'
        return data

    def device(self,name,args):
        self.calls.append((name,args))
        if name=='get_channel_config':return self.config()
        if name=='set_channel_state':
            target=self.channels[args['channel']]
            target.update({k:v for k,v in args.items() if k in ('name','mode')})
            target['enabled']=target.get('mode')!='off'
            return self.config()
        if name=='set_body_map':
            for part in args['parts']:
                self.channels[part['channel']]['name']=part['name']
            return args
        raise ConnectionError('fixture offline')

    def tearDown(self):
        self.c.db.close();self.temp.cleanup()

    def event(self,seq,phase='start',age=2,channel=0,touch=None,**extra):
        event=dict(seq=seq,channel=channel,phase=phase,touch_id=touch or 'touch'+str(seq),body_part='历史头',
                   sensor_type='pressure',direction='input',source='sensor',unit='adc_raw',quality='ok',
                   delivery_quality='live',peak_raw=2400,duration_ms=200)
        event.update(extra)
        with self.c.lock,self.c.db:
            self.c.db.execute('INSERT INTO events(device,boot,seq,at,payload) VALUES(?,?,?,?,?)',
                              ('fixture','boot',seq,self.now-age,json.dumps(event)))

    def test_defaults_partial_preferences_and_atomic_errors(self):
        e=self.c.experience
        self.assertEqual(e.preferences(),{'chat_integration_enabled':True,'proactive_enabled':False,'persona_source':'chat','doll_persona':''})
        e.update_preferences({'feedback':{'preferred_address':'亲爱的'}})
        self.assertEqual(self.c.bridge.preferences()['feedback']['tone'],'温柔自然')
        self.assertFalse(e.preferences()['proactive_enabled'])
        before=self.c.bridge.preferences()
        with self.assertRaises(ValueError):e.update_preferences({'feedback':{'tone':'别保存'},'policy':{'merge_ms':-1}})
        self.assertEqual(before,self.c.bridge.preferences())
        with self.assertRaises(ValueError):e.update_preferences({'proactive_enabled':1})

    def test_queue_delivery_gate_exposes_quiet_policy_without_needing_fresh_events(self):
        e=self.c.experience
        self.assertFalse(e.context('queue-chat')['proactive_delivery_allowed'])
        e.update_preferences({'proactive_enabled':True})
        self.assertTrue(e.context('queue-chat')['proactive_delivery_allowed'])
        e.update_preferences({'policy':{'quiet_hours':{'enabled':True,'start':'00:00','end':'00:00'}}})
        self.assertFalse(e.context('queue-chat')['proactive_delivery_allowed'])

    def test_leased_context_retains_five_rapid_touches_after_first_reply(self):
        e=self.c.experience
        e.update_preferences({'proactive_enabled':True})
        with patch.object(self.c,'sync'):session=self.c.start('queue-five',duration_sec=60)
        self.now=time.time()
        self.event(1,age=0)
        with self.c.db:self.c.db.execute('UPDATE events SET session_id=?',(session['id'],))
        first=e.context('queue-five',session_id=session['id'],through=1)
        e.acknowledge('queue-five',first['receipt_id'])
        for seq in range(2,7):self.event(seq,age=-seq/10)
        with self.c.db:self.c.db.execute('UPDATE events SET session_id=?',(session['id'],))
        self.assertEqual(e.context('queue-five',after=1)['events'],[])
        pending=e.context('queue-five',after=1,through=6,session_id=session['id'])
        self.assertEqual([v['id'] for v in pending['events']],[2,3,4,5,6])
        self.assertEqual(e.context('queue-five',after=1,through=6,session_id=session['id'])['receipt_id'],pending['receipt_id'])
        with self.assertRaises(ValueError):e.context('another-chat',session_id=session['id'])
        with self.assertRaises(ValueError):e.context('queue-five',session_id='wrong')
        e.acknowledge('queue-five',pending['receipt_id'])
        self.assertFalse(e.context('queue-five',session_id=session['id'])['events'])
        self.assertEqual(len(self.c.device_history()['events']),6)

    def test_names_only_preserves_other_channels_and_calibration(self):
        before=json.loads(json.dumps(self.channels))
        result=self.c.call('update_body_part',{'channel':0,'changes':{'name':'头顶','aliases':['脑袋'],'feedback_level':'light'}})
        self.assertTrue(result['updated']);self.assertEqual(result['name_sync'],'confirmed')
        self.assertEqual([n for n,_ in self.calls],['get_channel_config','set_body_map'])
        self.assertEqual(self.channels[0]['options'],before[0]['options'])
        self.assertEqual(self.channels[1],before[1]);self.assertEqual(self.c.experience.body(0)['aliases'],['脑袋'])
        self.event(1);self.assertEqual(self.c.experience.context('chat')['events'][0]['body_part'],'历史头')

    def test_port_patch_preserves_binding_calibration_and_other_ports(self):
        self.port_states=True
        self.channels[0]['mode']='connected';self.channels[1]['mode']='off';self.save_config()
        before=json.loads(json.dumps(self.channels))
        result=self.c.experience.update_body(0,{'mode':'simulation','name':'头顶'})
        self.assertTrue(result['updated']);self.assertEqual(result['port_sync'],'confirmed')
        self.assertEqual(self.calls[-1],('set_channel_state',{'channel':0,'name':'头顶','mode':'simulation'}))
        self.assertEqual(self.channels[0]['options'],before[0]['options'])
        self.assertEqual(self.channels[0]['mux_port'],before[0]['mux_port'])
        self.assertEqual(self.channels[1],before[1])
        self.assertEqual(self.c.experience.channels()[1]['mode'],'off')

    def test_legacy_and_failed_port_sync_are_not_queued(self):
        result=self.c.experience.update_body(0,{'mode':'off','aliases':['不要保存']})
        self.assertFalse(result['updated']);self.assertEqual(self.calls,[('get_channel_config',{})])
        self.assertEqual(self.c.experience.body(0)['aliases'],[])
        self.port_states=True;self.save_config();normal=self.device
        def uncertain(name,args):
            if name=='set_channel_state':raise TimeoutError('write result unknown')
            return normal(name,args)
        self.c.device=uncertain
        result=self.c.experience.update_body(0,{'mode':'off'})
        self.assertFalse(result['updated']);self.assertTrue(result['requires_refresh'])
        self.assertTrue(self.channels[0]['enabled'])

    def test_explicit_port_state_filters_unread_source_events(self):
        self.port_states=True
        self.channels[0]['mode']='connected';self.channels[1]['mode']='simulation';self.save_config()
        self.event(1,channel=0,source='simulation')
        self.event(2,channel=1,source='sensor')
        self.event(3,channel=0,source='sensor')
        self.event(4,channel=1,source='simulation')
        self.assertEqual([e['id'] for e in self.c.experience.context('chat')['events']],[3,4])
        self.c.experience.update_body(0,{'mode':'off'})
        self.assertEqual([e['id'] for e in self.c.experience.context('chat')['events']],[4])

    def test_persona_preferences_migrate_without_erasing_saved_persona(self):
        self.c.set_setting('companion_preferences',json.dumps({'proactive_enabled':True}))
        self.c.set_setting('persona','原来的娃娃人设')
        self.assertEqual(self.c.experience.preferences()['persona_source'],'chat')
        self.assertEqual(self.c.experience.context('chat')['persona_priority'],'current_chat')
        self.c.experience.update_preferences({'persona_source':'doll','doll_persona':'新的互动人设'})
        self.assertEqual(self.c.experience.context('chat')['persona_priority'],'saved_doll')
        self.c.experience.update_preferences({'persona_source':'chat'})
        self.assertEqual(self.c.experience.preferences()['doll_persona'],'新的互动人设')
        self.assertEqual(self.c.setting('persona'),'原来的娃娃人设')

    def test_offline_metadata_saves_but_failed_name_is_not_queued(self):
        self.c.device=lambda *args: (_ for _ in ()).throw(ConnectionError('offline'))
        self.assertTrue(self.c.experience.update_body(0,{'aliases':['脑袋']})['updated'])
        result=self.c.experience.update_body(0,{'name':'未同步','aliases':['不能保存']})
        self.assertFalse(result['updated']);self.assertEqual(self.c.experience.body(0)['aliases'],['脑袋'])
        self.assertEqual(self.c.experience.channels()[0]['name'],'头')
        with self.assertRaises(ValueError):self.c.experience.update_body(0,{'options':{}})

    def test_receipt_stability_isolation_restart_and_release(self):
        self.event(1);self.event(2,phase='end',touch='touch1',age=1)
        a=self.c.experience.context('a');again=self.c.experience.context('a')
        self.assertEqual(a['receipt_id'],again['receipt_id']);self.assertEqual(len(a['events']),1)
        self.assertEqual(len(a['updates']),1)
        with self.assertRaises(ValueError):self.c.experience.acknowledge('b',a['receipt_id'])
        self.c.experience.acknowledge('a',a['receipt_id'])
        self.assertTrue(self.c.experience.acknowledge('a',a['receipt_id'])['duplicate'])
        self.assertEqual(self.c.experience.context('a')['events'],[])
        self.assertEqual(len(self.c.experience.context('b')['events']),1)
        self.c.db.close();self.c=Companion(self.path,None,threading.Lock())
        self.assertEqual(self.c.experience.context('a')['events'],[])

    def test_freshness_fault_output_simulation_and_muted_body(self):
        self.event(1,age=40);self.event(2,quality='fault');self.event(3,direction='output')
        self.event(4,delivery_quality='offline_replay');self.event(5,source='simulation',channel=1)
        self.c.experience.update_body(0,{'feedback_level':'off'})
        self.event(6)
        context=self.c.experience.context('a');self.assertEqual([e['id'] for e in context['events']],[5])
        self.c.experience.update_preferences({'policy':{'allow_simulation':False}})
        self.assertEqual(self.c.experience.context('a')['events'],[])

    def test_merge_and_following_cooldown_not_duplicate(self):
        self.event(1,age=4);self.event(2,age=3.8,touch='second')
        ctx=self.c.experience.context('a');self.assertEqual(len(ctx['response_groups']),1)
        self.c.experience.acknowledge('a',ctx['receipt_id'])
        self.event(3,age=3,touch='third')
        self.assertEqual(self.c.experience.context('a')['events'],[])
        self.event(4,age=1,touch='fourth');self.assertEqual(len(self.c.experience.context('a')['events']),1)

    def test_pause_invalidates_receipts_and_pending_generation(self):
        self.event(1);ctx=self.c.experience.context('a')
        self.c.experience.update_preferences({'chat_integration_enabled':False})
        self.assertEqual(self.c.experience.context('a')['events'],[])
        with self.assertRaises(ValueError):self.c.experience.acknowledge('a',ctx['receipt_id'])
        self.c.experience.update_preferences({'chat_integration_enabled':True,'policy':{'quiet_hours':{'enabled':True,'start':'00:00','end':'00:00'}}})
        self.assertEqual(self.c.experience.context('a')['events'],[])

    def test_settings_overview_and_alias_collisions_are_data(self):
        self.c.experience.update_body(0,{'aliases':['头','同名']})
        self.c.experience.update_body(1,{'aliases':['同名']})
        self.assertEqual(len([c for c in self.c.experience.channels() if '同名' in c['aliases']]),2)
        self.assertFalse(self.c.experience.settings_entry()['browser_opened'])
        with self.assertRaises(ValueError):self.c.experience.settings_entry('invalid')
        overview=self.c.experience.overview();self.assertFalse(overview['online']);self.assertFalse(overview['proactive_available'])
        self.assertEqual(overview['values'],[])

    def test_proactive_switch_and_body_level(self):
        with self.c.db:self.c.db.execute("INSERT INTO sessions VALUES('s','chat',?,NULL,?,300,NULL)",(self.now-1,self.now))
        sub=self.c.bridge.subscribe('owner','chat','s','fixture',now=self.now)
        self.event(1)
        event=json.loads(self.c.db.execute('SELECT payload FROM events WHERE seq=1').fetchone()[0])
        self.c.bridge.enqueue(1,'fixture',self.now+.1,'s',event,self.now+.1)
        self.assertEqual(self.c.db.execute('SELECT COUNT(*) FROM bridge_outbox').fetchone()[0],0)
        self.c.experience.update_preferences({'proactive_enabled':True})
        self.c.bridge.enqueue(1,'fixture',self.now+.1,'s',event,self.now+.1)
        delivery=self.c.bridge.claim('owner',sub['id'],now=self.now+1)
        self.assertIsNotNone(delivery)
        self.c.experience.update_preferences({'proactive_enabled':False})
        with self.assertRaises(ValueError):self.c.bridge.renew('owner',sub['id'],delivery['event_id'],delivery['lease'])


if __name__=='__main__':unittest.main()
