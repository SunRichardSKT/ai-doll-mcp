"""Persistent touch archive and interaction sessions. Device transport is injected."""
import datetime as dt
import json
import sqlite3
import threading
import time
import uuid
import re
from interaction_bridge import EventBridge


def utcnow():
    return time.time()


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
        CREATE TABLE IF NOT EXISTS touches(id INTEGER PRIMARY KEY AUTOINCREMENT,
          device TEXT,touch_id TEXT,channel INTEGER,body_part TEXT,source TEXT,
          started REAL,ended REAL,duration_ms INTEGER,peak_raw INTEGER,session_id TEXT,
          UNIQUE(device,touch_id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
          device TEXT,boot TEXT,seq INTEGER,at REAL,payload TEXT,
          UNIQUE(device,boot,seq));
        CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY,at REAL,message TEXT);
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
        self.db.commit()
        self.error = None
        self.last_sync = None
        self.stop = threading.Event()
        self.sync_lock = threading.Lock()
        self.bridge = EventBridge(self)

    def setting(self, key, default=''):
        with self.lock:
            row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, value))

    def device(self, name, args):
        with self.serial_lock:
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
        received = received or utcnow()
        device, boot = batch['device_id'], batch['boot_id']
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM boots WHERE device=? AND boot=?', (device, boot)).fetchone()
            offset = row['offset'] if row else received-batch['uptime_ms']/1000
            cursor = row['cursor'] if row else 0
            if batch.get('gap') and batch['oldest_seq']-1 > cursor:
                self.db.execute('INSERT INTO notices(at,message) VALUES(?,?)',
                                (received, 'Device queue overflow: some touch events were lost.'))
            for event in batch['events']:
                seq = event['seq']
                if seq <= cursor:
                    continue
                at = offset+event['uptime_ms']/1000
                # Preserve occurrence-time ownership for every type; a pressure release keeps
                # the session of its start even if the chat ended while it was held.
                pressure = event.get('sensor_type', 'pressure') == 'pressure'
                session = self.db.execute('SELECT id FROM sessions WHERE started<=? '
                    'AND (ended IS NULL OR ended>?) AND last_activity+timeout>=? '
                    'ORDER BY started DESC LIMIT 1', (at, at, at)).fetchone()
                sid = session[0] if session else None
                if pressure and event['phase'] == 'end':
                    start = self.db.execute('SELECT session_id FROM touches WHERE device=? AND touch_id=?',
                                           (device, event.get('touch_id'))).fetchone()
                    sid = start[0] if start else None
                inserted = self.db.execute('INSERT OR IGNORE INTO events(device,boot,seq,at,payload,session_id) VALUES(?,?,?,?,?,?)',
                    (device, boot, seq, at, json.dumps(event, ensure_ascii=False), sid))
                if not inserted.rowcount:
                    continue
                if pressure and event['phase'] == 'start':
                    # Use occurrence time, not collection time, to exclude old buffered touches.
                    self.db.execute('INSERT OR IGNORE INTO touches(device,touch_id,channel,body_part,source,started,peak_raw,session_id) '
                        'VALUES(?,?,?,?,?,?,?,?)', (device, event['touch_id'], event['channel'], event['body_part'],
                        event['source'], at, event['peak_raw'], sid))
                    if sid:
                        self.db.execute('UPDATE sessions SET last_activity=MAX(last_activity,?) WHERE id=?', (at, sid))
                elif pressure and event['phase'] == 'end':
                    self.db.execute('UPDATE touches SET ended=?,duration_ms=?,peak_raw=? WHERE device=? AND touch_id=?',
                        (at, event['duration_ms'], event['peak_raw'], device, event['touch_id']))
                # Periodic temperature samples and AI output commands do not prolong
                # an idle interaction indefinitely. Pressure starts remain activity.
                self.bridge.enqueue(inserted.lastrowid, device, at, sid, event, received)
            self.db.execute('INSERT OR REPLACE INTO boots VALUES(?,?,?,?)',
                            (device, boot, offset, max(cursor, batch['next_cursor'])))
            self.expire(received)
        self.last_sync, self.error = received, None

    def sync(self):
        with self.sync_lock:
            # Persist each page before advancing the cursor, so reconnects cannot duplicate history.
            with self.lock:
                row = self.db.execute('SELECT * FROM boots ORDER BY offset DESC LIMIT 1').fetchone()
            boot, after = (row['boot'], row['cursor']) if row else ('', 0)
            for _ in range(8):
                with self.serial_lock:
                    batch = self.exchange({'cmd': 'events', 'boot_id': boot, 'after': after})
                if 'events' not in batch:
                    raise ValueError('Firmware does not provide touch events; update firmware first')
                self.ingest(batch)
                boot, after = batch['boot_id'], batch['next_cursor']
                if after >= batch['latest_seq']:
                    break

    def collect(self):
        while not self.stop.is_set():
            try:
                self.sync()
            except Exception as exc:
                self.error = type(exc).__name__ + ': device collection unavailable'
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
            return dict(self.db.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone())

    def end(self, session_id):
        self.sync()
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
        if name in ('doll_get_status', 'doll_set_led', 'doll_simulate_press', 'get_body_map', 'set_body_map', 'get_touch_events', 'get_sensor_config', 'set_sensor_config',
                    'get_channel_capabilities', 'get_channel_config', 'set_channel_config', 'read_channel_values',
                    'simulate_channel_input', 'set_input_enabled', 'set_output_enabled', 'set_vibration'):
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
        if name == 'set_persona':
            persona = args.get('persona')
            if not isinstance(persona, str) or len(persona) > 4000:
                raise ValueError('persona must be text up to 4000 characters')
            self.set_setting('persona', persona)
            return {'persona': persona}
        raise ValueError('Unknown tool')

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
                entries.append(dict(payload,id=row['id'],device=row['device'],at=row['at'],session_id=row['session_id']))
            notices=[dict(r) for r in self.db.execute('SELECT * FROM notices ORDER BY id DESC LIMIT 5')]
        return {'events':entries,'next_cursor':entries[-1]['id'] if entries else after,'has_more':len(rows)>limit,
                'timezone':'Asia/Shanghai','persona':self.setting('persona'),'notices':notices,
                'collector_error':self.error,'last_sync':self.last_sync,
                'interpretation':'Preserve type/unit/source/quality. Pressure raw is not calibrated force. Temperature is NTC estimate. Output events are commands, not touch or measured motor feedback.'}

