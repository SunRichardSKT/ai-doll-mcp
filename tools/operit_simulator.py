"""Developer-only simulation for the current Operit tools; never opens an ESP32 port."""
import json
import threading
import time
import uuid

from companion import Companion
from private_storage import private_directory


class SimulationBackend:
    def __init__(self,folder,delay=3):
        self.folder=private_directory(folder)
        self.c=Companion(self.folder/'simulation.sqlite3',None,threading.Lock())
        self.delay=delay
        self.stop=threading.Event()
        self.threads=[]
        self.c.sync=lambda:None
        self.c.device=self.device
        self.c.set_setting('collector_last_device','operit-demo-not-hardware')
        self.c.set_setting('cached_get_channel_config',json.dumps({'saved_at':time.time(),'data':{'channels':[
            {'channel':0,'name':'头顶（演示）','enabled':True,'type':'pressure','driver':'mux_adc'}]}}))
        self.c.experience.update_preferences({'proactive_enabled':True})

    def device(self,name,args):
        if name=='doll_get_status':
            return {'device_id':'operit-demo-not-hardware','firmware':'simulation-only',
                    'sensor_mode':'simulation','physical_outputs_enabled':False,'wifi_connected':False,
                    'demo':True,'hardware_verified':False}
        if name=='get_channel_config':return self.c.call('get_cached_channel_config',{})
        raise ValueError('Demo does not control hardware')

    def call(self,name,args):
        result=self.c.call(name,args)
        if name=='start_interaction':
            with self.c.lock,self.c.db:
                self.c.db.execute('CREATE TABLE IF NOT EXISTS demo_started(session TEXT PRIMARY KEY)')
                created=self.c.db.execute('INSERT OR IGNORE INTO demo_started VALUES(?)',(result['id'],)).rowcount
            if created:
                thread=threading.Thread(target=self.emit,args=(result['id'],),daemon=True)
                self.threads.append(thread);thread.start()
        if isinstance(result,dict):result=dict(result,demo=True,hardware_verified=False)
        return result

    def emit(self,session_id):
        touch=uuid.uuid4().hex
        for phase,delay in [('start',self.delay),('end',2)]:
            if self.stop.wait(delay):return
            current=self.c.active()
            if not current or current['id']!=session_id:return
            now=time.time()
            with self.c.lock,self.c.db:
                seq=self.c.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events').fetchone()[0]
                event={'seq':seq,'channel':0,'touch_id':touch,'phase':phase,'body_part':'头顶（演示）',
                       'sensor_type':'pressure','direction':'input','source':'simulation','quality':'ok',
                       'unit':'adc_raw','delivery_quality':'live','value':3200 if phase=='start' else 0,
                       'duration_ms':0 if phase=='start' else 2000}
                self.c.db.execute('INSERT INTO events(device,boot,seq,at,payload,session_id) VALUES(?,?,?,?,?,?)',
                    ('operit-demo-not-hardware','demo-boot',seq,now,json.dumps(event,ensure_ascii=False),session_id))
                self.c.last_sync=now

    def close(self):
        self.stop.set()
        for thread in self.threads:thread.join(timeout=2)
        self.c.db.close()
