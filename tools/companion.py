"""Persistent touch archive and interaction sessions. Device transport is injected."""
import datetime as dt
import json
import sqlite3
import threading
import time
import uuid
import re
import sys
from contextlib import contextmanager
from importlib.metadata import version as package_version, PackageNotFoundError
from interaction_bridge import EventBridge
from input_observations import pressure_observations


def utcnow():
    return time.time()


class DeviceBusyError(TimeoutError):
    """An operation was not started because the device connection is occupied."""


@contextmanager
def bounded_device_lock(lock):
    # A waiting HTTP/MCP request must expire before it becomes a late output.
    # This bounds queue time, not the transport's own in-flight network timeout.
    if not lock.acquire(timeout=2):
        raise DeviceBusyError('Device connection busy; operation was not started')
    try:
        yield
    finally:
        lock.release()


class Companion:
    def __init__(self, path, exchange, serial_lock):
        self.exchange, self.serial_lock = exchange, serial_lock
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS boots(device TEXT,boot TEXT,offset REAL,cursor INTEGER,
          PRIMARY KEY(device,boot));
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,chat_id TEXT,started REAL,
          ended REAL,last_activity REAL,timeout INTEGER,reason TEXT);
        CREATE TABLE IF NOT EXISTS session_boundaries(session_id TEXT PRIMARY KEY,
          device TEXT,boot TEXT,seq INTEGER);
        CREATE TABLE IF NOT EXISTS touches(id INTEGER PRIMARY KEY AUTOINCREMENT,
          device TEXT,touch_id TEXT,channel INTEGER,body_part TEXT,source TEXT,
          started REAL,ended REAL,duration_ms INTEGER,peak_raw INTEGER,session_id TEXT,
          UNIQUE(device,touch_id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
          device TEXT,boot TEXT,seq INTEGER,at REAL,payload TEXT,
          UNIQUE(device,boot,seq));
        CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY,at REAL,message TEXT);
        CREATE TABLE IF NOT EXISTS storage_cursors(device TEXT,epoch TEXT,cursor INTEGER,
          lost INTEGER,corrupt INTEGER,failures INTEGER,last_boot TEXT,PRIMARY KEY(device,epoch));
        ''')
        # Upgrade existing archives in place; no table is replaced or history removed.
        if 'session_id' not in {row['name'] for row in self.db.execute('PRAGMA table_info(events)')}:
            self.db.execute('ALTER TABLE events ADD COLUMN session_id TEXT')
            for row in self.db.execute('SELECT id,device,payload FROM events').fetchall():
                payload = json.loads(row['payload'])
                touch = self.db.execute('SELECT session_id FROM touches WHERE device=? AND touch_id=?',
                                        (row['device'], payload.get('touch_id'))).fetchone()
                if touch and touch['session_id']:
                    self.db.execute('UPDATE events SET session_id=? WHERE id=?', (touch['session_id'],row['id']))
        if 'time_quality' not in {row['name'] for row in self.db.execute('PRAGMA table_info(touches)')}:
            self.db.execute("ALTER TABLE touches ADD COLUMN time_quality TEXT DEFAULT 'legacy_estimate'")
        self.db.commit()
        self.error = None
        self.last_sync = None
        self.stop = threading.Event()
        self.sync_lock = threading.Lock()
        self.last_clock_sync = 0
        self.bridge = EventBridge(self)
        from history_management import HistoryManager
        self.history_manager=HistoryManager(self)
        self.maintenance_error=None

    def setting(self, key, default=''):
        with self.lock:
            row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, value))

    def device_connection(self):
        return bounded_device_lock(self.serial_lock)

    def device(self, name, args):
        with self.device_connection():
            r = self.exchange({'cmd': 'rpc', 'request': {'jsonrpc': '2.0', 'id': 1,
                'method': 'tools/call', 'params': {'name': name, 'arguments': args}}})
        if 'error' in r:
            raise ValueError(str(r['error']))
        result = r['result']
        if result.get('isError'):
            raise ValueError('Device tool failed')
        return json.loads(result['content'][0]['text'])

    def expire(self, now=None):
        now = now or utcnow()
        self.db.execute("UPDATE sessions SET ended=last_activity+timeout,reason='idle_timeout' "
                        'WHERE ended IS NULL AND last_activity+timeout<?', (now,))

    def ingest(self, batch, received=None):
        received = utcnow() if received is None else received
        device, boot = batch['device_id'], batch['boot_id']
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM boots WHERE device=? AND boot=?', (device, boot)).fetchone()
            offset = row['offset'] if row and row['offset'] is not None else received-batch['uptime_ms']/1000
            cursor = row['cursor'] if row else 0
            storage = batch.get('event_storage')
            if batch.get('gap') and batch['oldest_seq']-1 > cursor and not (storage and storage.get('available')):
                self.db.execute('INSERT INTO notices(at,message) VALUES(?,?)',
                                (received, 'Device queue overflow: some touch events were lost.'))
            # Persistent cursors are independent of RAM sequence cursors. A RAM page
            # can contain later events while earlier flash pages still await recovery.
            if storage and storage.get('available'):
                epoch = storage.get('storage_epoch')
                if not isinstance(epoch,str) or not re.fullmatch('[0-9a-f]{32}',epoch):
                    raise ValueError('Invalid persistent storage epoch')
                old = self.db.execute('SELECT * FROM storage_cursors WHERE device=? AND epoch=?',(device,epoch)).fetchone()
                stored_cursor = old['cursor'] if old else 0
                seen = 0
                entries = batch.get('persistent_events',[])
                if not isinstance(entries,list) or len(entries)>24:
                    raise ValueError('Invalid persistent page')
                for entry in entries:
                    ident, event_boot, event = entry.get('storage_id'), entry.get('boot_id'), entry.get('event')
                    if (type(ident) is not int or not seen < ident <= 9007199254740991 or
                            not isinstance(event_boot,str) or not 1<=len(event_boot)<=128 or not isinstance(event,dict)):
                        raise ValueError('Invalid persistent event identity/order')
                    seen = ident
                    if ident<=stored_cursor:
                        continue
                    prior = self.db.execute('SELECT * FROM boots WHERE device=? AND boot=?',(device,event_boot)).fetchone()
                    anchor = offset if event_boot==boot else (prior['offset'] if prior else None)
                    event = dict(event,storage_id=ident,storage_epoch=epoch,boot_id=event_boot)
                    at, quality = self.event_time(event,anchor)
                    replay = (event_boot!=boot or not 0<=batch['uptime_ms']-event.get('uptime_ms',0)<=5000)
                    event.update(time_quality=quality,delivery_quality='offline_replay' if replay else 'live',received_at=received)
                    self.archive_event(device,event_boot,event,at,received)
                    if not prior and event_boot!=boot:
                        self.db.execute('INSERT INTO boots VALUES(?,?,?,?)',(device,event_boot,anchor,0))
                    stored_cursor=ident
                reported=batch.get('storage_cursor',0)
                if type(reported) is not int or reported!=seen:
                    raise ValueError('Persistent page cursor does not match its events')
                counts=[]
                for key,column in [('lost_records','lost'),('corrupt_records','corrupt'),('write_failures_since_boot','failures')]:
                    value=storage.get(key,0)
                    if type(value) is not int or value<0:raise ValueError('Invalid storage counters')
                    previous=old[column] if old and (column!='failures' or old['last_boot']==boot) else 0
                    if value>previous:
                        self.db.execute('INSERT INTO notices(at,message) VALUES(?,?)',
                            (received,f'Device persistent queue {key}: {value-previous} additional records affected.'))
                    counts.append(value)
                self.db.execute('INSERT OR REPLACE INTO storage_cursors VALUES(?,?,?,?,?,?,?)',
                    (device,epoch,stored_cursor,*counts,boot))
            for event in batch['events']:
                seq = event['seq']
                if seq <= cursor:
                    continue
                at, quality = self.event_time(event,offset)
                event=dict(event,time_quality=quality,received_at=received)
                if storage is not None:
                    replay=not 0<=batch['uptime_ms']-event['uptime_ms']<=5000
                    event['delivery_quality']='offline_replay' if replay else 'live'
                self.archive_event(device,boot,event,at,received)
            self.db.execute('INSERT OR REPLACE INTO boots VALUES(?,?,?,?)',
                            (device, boot, offset, max(cursor, batch['next_cursor'])))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('collector_last_boot',boot))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('collector_last_device',device))
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('collector_last_seq',str(batch['latest_seq'])))
            self.expire(received)
        self.last_sync, self.error = received, None

    @staticmethod
    def event_time(event,offset):
        uptime=event.get('uptime_ms')
        if type(uptime) is not int or uptime<0:
            raise ValueError('Invalid event uptime')
        clock=event.get('device_time_ms')
        if event.get('time_quality')=='device_clock':
            if type(clock) is not int or not 1704067200000<=clock<=4102444800000:
                raise ValueError('Invalid device clock timestamp')
            return clock/1000,'device_clock'
        if offset is not None:
            return offset+uptime/1000,'estimated_from_boot_anchor'
        return None,'unknown'

    def archive_event(self,device,boot,event,at,received):
        seq=event['seq']
        if type(seq) is not int or seq<=0:
            raise ValueError('Invalid event sequence')
        if self.db.execute('SELECT 1 FROM deleted_events WHERE device=? AND boot=? AND seq=?',(device,boot,seq)).fetchone():
            return
        if event.get('touch_id') and self.db.execute('SELECT 1 FROM deleted_touches WHERE device=? AND touch_id=?',
                                                   (device,event['touch_id'])).fetchone():
            self.db.execute('INSERT OR IGNORE INTO deleted_events VALUES(?,?,?)',(device,boot,seq))
            return
        pressure=event.get('sensor_type','pressure')=='pressure'
        session=self.db.execute('SELECT id FROM sessions WHERE started<=? '
            'AND (ended IS NULL OR ended>?) AND last_activity+timeout>=? '
            'ORDER BY started DESC LIMIT 1',(at,at,at)).fetchone() if at is not None else None
        sid=session[0] if session else None
        if sid:
            boundary=self.db.execute('SELECT * FROM session_boundaries WHERE session_id=?',(sid,)).fetchone()
            if boundary and boundary['device']==device and boundary['boot']==boot and seq<=boundary['seq']:
                sid=None
        if sid is None and at is not None and event.get('delivery_quality')=='live':
            # Device UTC can lag the host by a small transport delay. A new
            # sequence after an explicit session boundary proves membership;
            # preserve its original timestamp rather than rewriting history.
            boundary=self.db.execute('SELECT s.id,s.started,b.seq FROM sessions s JOIN session_boundaries b '
                'ON b.session_id=s.id WHERE s.ended IS NULL AND b.device=? AND b.boot=? '
                'AND b.seq<? AND s.started>? AND s.started<=? AND s.started<=? '
                'AND s.last_activity+s.timeout>=? ORDER BY s.started DESC LIMIT 1',
                (device,boot,seq,at,at+2,received,received)).fetchone()
            if boundary:sid=boundary['id'];event=dict(event,session_time_quality='sequence_boundary')
        if pressure and event['phase']=='end':
            start=self.db.execute('SELECT session_id FROM touches WHERE device=? AND touch_id=?',
                                  (device,event.get('touch_id'))).fetchone()
            sid=start[0] if start else None
        inserted=self.db.execute('INSERT OR IGNORE INTO events(device,boot,seq,at,payload,session_id) VALUES(?,?,?,?,?,?)',
            (device,boot,seq,at,json.dumps(event,ensure_ascii=False),sid))
        if not inserted.rowcount:return
        if pressure and event['phase']=='start':
            self.db.execute('INSERT OR IGNORE INTO touches(device,touch_id,channel,body_part,source,started,peak_raw,session_id,time_quality) VALUES(?,?,?,?,?,?,?,?,?)',
                (device,event['touch_id'],event['channel'],event['body_part'],event['source'],at,event['peak_raw'],sid,event.get('time_quality','legacy_estimate')))
            if sid and event.get('delivery_quality')!='offline_replay':
                self.db.execute('UPDATE sessions SET last_activity=MAX(last_activity,?) WHERE id=?',(at,sid))
        elif pressure and event['phase']=='end':
            self.db.execute('UPDATE touches SET ended=?,duration_ms=?,peak_raw=? WHERE device=? AND touch_id=?',
                (at,event['duration_ms'],event['peak_raw'],device,event['touch_id']))
        self.bridge.enqueue(inserted.lastrowid,device,at,sid,event,received)

    def sync(self):
        with bounded_device_lock(self.sync_lock):
            # Persist each page before advancing the cursor, so reconnects cannot duplicate history.
            with self.lock:
                row = self.db.execute('SELECT * FROM boots WHERE boot=? ORDER BY offset DESC LIMIT 1',
                                      (self.setting('collector_last_boot'),)).fetchone()
                if row is None:row=self.db.execute('SELECT * FROM boots ORDER BY offset DESC LIMIT 1').fetchone()
            boot, after = (row['boot'], row['cursor']) if row else ('', 0)
            for _ in range(8):
                with self.device_connection():
                    batch = self.exchange({'cmd': 'events', 'boot_id': boot, 'after': after})
                if 'events' not in batch:
                    raise ValueError('Expected an event page; received fields: '+','.join(sorted(batch)))
                received=utcnow()
                self.ingest(batch,received)
                storage=batch.get('event_storage',{})
                if storage.get('available') and batch.get('storage_cursor'):
                    # Commit has completed above. A lost ACK only causes deduplicated replay.
                    with self.device_connection():
                        ack=self.exchange(dict(cmd='ack_events',boot_id=batch['boot_id'],
                            storage_epoch=storage['storage_epoch'],storage_cursor=batch['storage_cursor']))
                    if ack.get('error'):raise ValueError('Persistent event acknowledgement failed')
                if storage and (not storage.get('clock_synced') or time.monotonic()-self.last_clock_sync>60):
                    clock=storage.get('device_time_ms',0)
                    if not storage.get('clock_synced') or abs(received*1000-clock)>2000:
                        with self.device_connection():
                            timed=self.exchange(dict(cmd='sync_time',boot_id=batch['boot_id'],unix_time_ms=round(utcnow()*1000)))
                        if timed.get('error'):raise ValueError('Device clock synchronization failed')
                    self.last_clock_sync=time.monotonic()
                boot, after = batch['boot_id'], batch['next_cursor']
                if after >= batch['latest_seq'] and not batch.get('storage_has_more'):
                    break

    def collect(self):
        while not self.stop.is_set():
            try:
                self.sync()
            except Exception as exc:
                self.error = type(exc).__name__ + ': device collection unavailable'
            try:
                self.history_manager.maintain()
                self.maintenance_error=None
            except Exception:
                self.maintenance_error='History retention unavailable; archive preserved'
            self.stop.wait(0.7)

    def active(self):
        with self.lock, self.db:
            self.expire()
            row = self.db.execute('SELECT * FROM sessions WHERE ended IS NULL LIMIT 1').fetchone()
            return dict(row) if row else None

    def start(self, chat_id='main', idle_timeout_sec=300):
        if not isinstance(chat_id, str) or not 1 <= len(chat_id) <= 128:
            raise ValueError('chat_id must be 1..128 characters')
        if type(idle_timeout_sec) is not int or not 30 <= idle_timeout_sec <= 3600:
            raise ValueError('idle_timeout_sec must be 30..3600')
        self.sync()  # Drain old events before setting the start boundary.
        with self.lock, self.db:
            current = self.active()
            if current:
                if current['chat_id'] != chat_id:
                    raise ValueError('Another chat already owns the active interaction; end it first')
                return current
            now, sid = utcnow(), uuid.uuid4().hex
            self.db.execute('INSERT INTO sessions VALUES(?,?,?,NULL,?,?,NULL)',
                            (sid, chat_id, now, now, idle_timeout_sec))
            device,boot=self.setting('collector_last_device'),self.setting('collector_last_boot')
            seq=self.setting('collector_last_seq')
            if device and boot and seq.isdigit():
                self.db.execute('INSERT INTO session_boundaries VALUES(?,?,?,?)',(sid,device,boot,int(seq)))
            return dict(self.db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone())

    def end(self, session_id):
        try:self.sync()
        except DeviceBusyError:self.error='Device connection busy; ending interaction with archived data'
        except Exception:self.error='Device offline; ending interaction with archived data'
        with self.lock, self.db:
            if not self.db.execute('SELECT id FROM sessions WHERE id=?', (session_id,)).fetchone():
                raise ValueError('Unknown session_id')
            self.db.execute("UPDATE sessions SET ended=?,reason='user' WHERE id=? AND ended IS NULL", (utcnow(), session_id))
            return dict(self.db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone())

    def history(self, date=None, body_part=None, session_id=None, after=0, limit=50):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('after >= 0 and limit 1..200 required')
        where, params = ['id>?'], [after]
        if date:
            day = dt.date.fromisoformat(date)
            tz = dt.timezone(dt.timedelta(hours=8))
            start = dt.datetime.combine(day, dt.time.min, tzinfo=tz).timestamp()
            where += ['started>=?', 'started<?']; params += [start, start+86400]
        for key, value in [('body_part', body_part), ('session_id', session_id)]:
            if value is not None:
                where.append(key+'=?'); params.append(value)
        with self.lock:
            rows = self.db.execute('SELECT * FROM touches WHERE '+' AND '.join(where)+' ORDER BY id LIMIT ?', params+[limit+1]).fetchall()
            more = len(rows) > limit
            entries = [dict(row) for row in rows[:limit]]
            notices = [dict(r) for r in self.db.execute('SELECT * FROM notices ORDER BY id DESC LIMIT 5')]
        return {'touches': entries, 'next_cursor': entries[-1]['id'] if entries else after,
                'has_more': more, 'timezone': 'Asia/Shanghai', 'persona': self.setting('persona'),
                'notices': notices, 'collector_error': self.error, 'last_sync': self.last_sync,
                'interpretation': 'Body names are user labels. Pressure is raw ADC, not calibrated force. Infer actions cautiously.'}

    def call(self, name, args):
        if not isinstance(args, dict):
            raise ValueError('arguments must be an object')
        history_methods={'export_history':'export','get_history_statistics':'statistics',
            'preview_history_deletion':'preview_delete','delete_history':'delete',
            'get_history_retention':'retention','set_history_retention':'set_retention',
            'preview_history_retention':'preview_retention'}
        if name in history_methods:
            return getattr(self.history_manager,history_methods[name])(**args)
        if name in ('doll_get_status', 'doll_set_led', 'doll_simulate_press', 'get_body_map', 'set_body_map', 'get_touch_events', 'get_sensor_config', 'set_sensor_config',
                    'get_channel_capabilities', 'get_channel_config', 'set_channel_config', 'read_channel_values', 'scan_input_devices',
                    'simulate_channel_input', 'set_input_enabled', 'set_output_enabled', 'set_vibration',
                    'get_operating_mode', 'set_operating_mode', 'capture_pressure_calibration',
                    'get_pressure_calibration', 'apply_pressure_calibration', 'cancel_pressure_calibration',
                    'get_event_storage_status'):
            return self.device(name, args)
        if name == 'get_interaction_status':
            return {'active_session': self.active(), 'collector_error': self.error, 'last_sync': self.last_sync}
        if name == 'start_interaction':
            return self.start(**args)
        if name == 'end_interaction':
            return self.end(**args)
        if name in ('query_touch_history', 'get_interaction_events', 'query_device_history', 'get_interaction_device_events'):
            if name in ('get_interaction_events','get_interaction_device_events'):
                with self.lock:
                    if not args.get('session_id') or not self.db.execute('SELECT id FROM sessions WHERE id=?',(args['session_id'],)).fetchone():
                        raise ValueError('Known session_id required')
            try:
                self.sync()
            except DeviceBusyError:
                self.error = 'Device connection busy; returning archived history'
            except Exception:
                self.error = 'Device offline; returning archived history'
            return self.device_history(**args) if name in ('query_device_history','get_interaction_device_events') else self.history(**args)
        if name == 'get_persona':
            return {'persona': self.setting('persona')}
        if name == 'get_feedback_preferences':
            return self.bridge.preferences()
        if name == 'set_feedback_preferences':
            return self.bridge.save_preferences(**args)
        if name == 'get_reply_bridge_status':
            return self.bridge.state()
        if name == 'summarize_interactions':
            try:self.sync()
            except DeviceBusyError:self.error = 'Device connection busy; returning archived history'
            except Exception:self.error = 'Device offline; returning archived history'
            history = self.device_history(**args)
            # Boot boundaries are required even when the usual public event view omits them.
            with self.lock:
                values = []
                for entry in history['events']:
                    row = self.db.execute('SELECT boot FROM events WHERE id=?',(entry['id'],)).fetchone()
                    values.append(dict(entry,boot=row['boot']))
            history['summary'] = pressure_observations(values,self.bridge.preferences()['policy'])
            history['summary']['scope'] = 'returned_page'
            return history
        if name == 'get_installation_status':
            return self.installation_status(**args)
        if name == 'discover_paired_device':
            callback = getattr(self, 'discovery_callback', None)
            if callback is None:
                return {'found': False, 'updated': False, 'message': 'Discovery is available in Wi-Fi transport only'}
            with self.device_connection():
                return callback(**args)
        if name == 'set_persona':
            persona = args.get('persona')
            if not isinstance(persona, str) or len(persona) > 4000:
                raise ValueError('persona must be text up to 4000 characters')
            self.set_setting('persona', persona)
            return {'persona': persona}
        raise ValueError('Unknown tool')

    def installation_status(self, client_kind='unknown'):
        if client_kind not in ('unknown','stdio','events','api'):
            raise ValueError('client_kind must be unknown, stdio, events or api')
        dependencies = {}
        for package in ('mcp','pyserial','tzdata'):
            try:dependencies[package] = package_version(package)
            except PackageNotFoundError:dependencies[package] = None
        live, error = None, None
        try:
            status = self.device('doll_get_status',{})
            live = {k:status.get(k) for k in ('device_id','firmware','wifi_connected','sensor_mode','physical_outputs_enabled')}
        except DeviceBusyError:error = 'Device connection busy; status was not refreshed'
        except Exception:error = 'Device unavailable; verify power, transport and LAN/serial connection'
        runtime = dict(getattr(self,'runtime_info',{}))
        with self.lock:
            self.db.execute('SELECT COUNT(*) FROM settings').fetchone()
        bridge = self.bridge.state()
        return dict(bridge=bridge['version'], python=sys.version.split()[0],
            dependencies=dependencies, database_open=True, runtime=runtime,
            device=live, device_error=error, collector_error=self.error,last_sync=self.last_sync,
            quiet_hours=bridge['quiet_hours'],
            client_kind=client_kind, client_registration='not_inspected', host_event_support='not_verified',
            next_steps=['Reconnect the AI client to refresh its advertised tool list.',
                'STDIO clients query or perform bounded waits; an idle chat is not awakened by a tool server.',
                'Events/API hosts must create a session and bind a subscription to the current target.',
                'Remote web AI needs an authenticated reachable endpoint; GitHub is documentation, not that endpoint.'],
            secrets_included=False)

    def device_history(self, date=None, body_part=None, sensor_type=None, direction=None,
                       session_id=None, after=0, limit=50):
        if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=200:
            raise ValueError('after >= 0 and limit 1..200 required')
        if (sensor_type is not None and (not isinstance(sensor_type,str) or not re.fullmatch('[a-z][a-z0-9_]{0,47}',sensor_type))) or direction not in (None,'input','output'):
            raise ValueError('Invalid sensor_type identifier or direction')
        where,params=['id>?'],[after]
        if date:
            day=dt.date.fromisoformat(date);tz=dt.timezone(dt.timedelta(hours=8))
            start=dt.datetime.combine(day,dt.time.min,tzinfo=tz).timestamp()
            where+=['at>=?','at<?'];params+=[start,start+86400]
        if session_id is not None:where.append('session_id=?');params.append(session_id)
        if body_part is not None:where.append("json_extract(payload,'$.body_part')=?");params.append(body_part)
        if sensor_type is not None:where.append("COALESCE(json_extract(payload,'$.sensor_type'),'pressure')=?");params.append(sensor_type)
        if direction is not None:where.append("COALESCE(json_extract(payload,'$.direction'),'input')=?");params.append(direction)
        with self.lock:
            rows=self.db.execute('SELECT * FROM events WHERE '+' AND '.join(where)+' ORDER BY id LIMIT ?',params+[limit+1]).fetchall()
            entries=[]
            for row in rows[:limit]:
                payload=json.loads(row['payload']);payload.setdefault('sensor_type','pressure');payload.setdefault('direction','input')
                payload.setdefault('unit','adc_raw');payload.setdefault('quality','ok')
                payload.setdefault('time_quality','legacy_estimate')
                entries.append(dict(payload,id=row['id'],device=row['device'],at=row['at'],session_id=row['session_id']))
            notices=[dict(r) for r in self.db.execute('SELECT * FROM notices ORDER BY id DESC LIMIT 5')]
        return {'events':entries,'next_cursor':entries[-1]['id'] if entries else after,'has_more':len(rows)>limit,
                'timezone':'Asia/Shanghai','persona':self.setting('persona'),'notices':notices,
                'collector_error':self.error,'last_sync':self.last_sync,
                'interpretation':'Preserve type/unit/source/quality. Pressure raw is not calibrated force. Temperature uses its configured driver; invalid readings stay null. Output events are commands, not touch or measured motor feedback.'}

