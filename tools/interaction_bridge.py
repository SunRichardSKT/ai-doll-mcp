"""Durable interaction outbox shared by local streams and MCP Events webhooks.

enqueue() runs in the same SQLite transaction as Companion.ingest(). Delivery is
at-least-once; consumers must deduplicate eventId before invoking their model.
"""
import datetime as dt
import hashlib
import json
import math
import re
import secrets
import time
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from input_observations import pressure_observations

VERSION = 'doll-bridge-2.7.0'
DEFAULT_QUIET = dict(enabled=False, start='23:00', end='07:00', timezone='Asia/Shanghai')
DEFAULT_POLICY = dict(merge_ms=300, cooldown_ms=1500, max_age_sec=30,
                      allow_simulation=True, temperature_enabled=False,
                      temperature_delta_c=1.0, notify_pressure_patterns=True,
                      long_press_ms=1500, tap_max_ms=600, tap_gap_ms=600,
                      simultaneous_ms=300, quiet_hours=DEFAULT_QUIET)
DEFAULT_FEEDBACK = dict(tone='温柔自然', max_characters=160, language='zh-CN',
                        preferred_address='', avoid_phrases=[])


def text(value, field, maximum=128):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'{field} must be nonempty text, at most {maximum} characters')
    return value


def validated_policy(value):
    if not isinstance(value, dict) or set(value)-set(DEFAULT_POLICY):
        raise ValueError('Unknown feedback policy fields')
    result = dict(DEFAULT_POLICY, **value)
    for k, lo, hi in [('merge_ms', 0, 1000), ('cooldown_ms', 0, 30000), ('max_age_sec', 1, 120),
                      ('long_press_ms', 500, 30000), ('tap_max_ms', 50, 2000),
                      ('tap_gap_ms', 50, 5000), ('simultaneous_ms', 0, 1000)]:
        if type(result[k]) is not int or not lo <= result[k] <= hi:
            raise ValueError(f'{k} outside supported range')
    for k in ['allow_simulation', 'temperature_enabled', 'notify_pressure_patterns']:
        if type(result[k]) is not bool:
            raise ValueError(k+' must be boolean')
    v = result['temperature_delta_c']
    if type(v) not in (int, float) or not math.isfinite(v) or not .1 <= v <= 30:
        raise ValueError('temperature_delta_c must be .1..30')
    if result['long_press_ms'] <= result['tap_max_ms']:
        raise ValueError('long_press_ms must exceed tap_max_ms')
    quiet = result['quiet_hours']
    if not isinstance(quiet, dict) or set(quiet)-set(DEFAULT_QUIET):
        raise ValueError('Unknown quiet_hours fields')
    quiet = dict(DEFAULT_QUIET, **quiet)
    if type(quiet['enabled']) is not bool:
        raise ValueError('quiet_hours.enabled must be boolean')
    for k in ['start', 'end']:
        if not isinstance(quiet[k], str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', quiet[k]):
            raise ValueError('quiet_hours times must be HH:MM')
    text(quiet['timezone'], 'quiet_hours.timezone', 64)
    try: ZoneInfo(quiet['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Unknown IANA timezone; install the tzdata dependency') from None
    result['quiet_hours'] = quiet
    return result


def quiet_status(policy, now):
    quiet = policy['quiet_hours']
    local = dt.datetime.fromtimestamp(now, ZoneInfo(quiet['timezone']))
    minute = local.strftime('%H:%M')
    start, end = quiet['start'], quiet['end']
    within = start == end or (start <= minute < end if start < end else minute >= start or minute < end)
    return dict(active=quiet['enabled'] and within, local_time=local.isoformat(), **quiet)


def validated_feedback(value):
    if not isinstance(value, dict) or set(value)-set(DEFAULT_FEEDBACK):
        raise ValueError('Unknown feedback preference fields')
    result = dict(DEFAULT_FEEDBACK, **value)
    text(result['tone'], 'tone', 1000); text(result['language'], 'language', 32)
    if type(result['max_characters']) is not int or not 20 <= result['max_characters'] <= 2000:
        raise ValueError('max_characters must be 20..2000')
    if not isinstance(result['preferred_address'], str) or len(result['preferred_address']) > 80:
        raise ValueError('preferred_address must be text up to 80 characters')
    if not isinstance(result['avoid_phrases'], list) or len(result['avoid_phrases']) > 20:
        raise ValueError('avoid_phrases must contain at most 20 phrases')
    for phrase in result['avoid_phrases']:text(phrase, 'avoid_phrases entry', 100)
    result['avoid_phrases'] = list(result['avoid_phrases'])
    return result


class EventBridge:
    def __init__(self, companion):
        self.c = companion
        self.lock, self.db = companion.lock, companion.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS bridge_subscriptions(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, target_id TEXT NOT NULL,
          session_id TEXT NOT NULL, device_id TEXT NOT NULL, transport TEXT NOT NULL,
          created REAL NOT NULL, expires REAL NOT NULL, active INTEGER NOT NULL,
          policy TEXT NOT NULL, feedback TEXT NOT NULL, callback TEXT, secret TEXT,
          arguments TEXT, next_allowed REAL NOT NULL DEFAULT 0, last_temp REAL);
        CREATE TABLE IF NOT EXISTS bridge_outbox(
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
          subscription_id TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL,
          ready REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, lease TEXT, lease_until REAL,
          last_error TEXT, delivered REAL);
        CREATE INDEX IF NOT EXISTS bridge_due ON bridge_outbox(state,ready);
        CREATE TABLE IF NOT EXISTS bridge_seen(
          subscription_id TEXT NOT NULL, event_row INTEGER NOT NULL,
          PRIMARY KEY(subscription_id,event_row));
        CREATE TABLE IF NOT EXISTS bridge_temperature_baselines(
          subscription_id TEXT NOT NULL, channel INTEGER NOT NULL, value REAL NOT NULL,
          PRIMARY KEY(subscription_id,channel));
        CREATE TABLE IF NOT EXISTS bridge_replies(
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
          subscription_id TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL,
          created REAL NOT NULL);
        ''')
        self.db.commit()

    def preferences(self):
        return dict(policy=validated_policy(json.loads(self.c.setting('bridge_policy', '{}'))),
                    feedback=validated_feedback(json.loads(self.c.setting('bridge_feedback', '{}'))))

    def save_preferences(self, policy, feedback):
        policy, feedback = validated_policy(policy), validated_feedback(feedback)
        with self.lock, self.db:
            for k, v in [('bridge_policy', policy), ('bridge_feedback', feedback)]:
                self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (k, json.dumps(v, ensure_ascii=False)))
            self.db.execute('UPDATE bridge_subscriptions SET policy=?,feedback=? WHERE active=1',
                            (json.dumps(policy), json.dumps(feedback, ensure_ascii=False)))
            self._expire(time.time())
        return dict(policy=policy, feedback=feedback)

    def _expire(self, now):
        self.c.expire(now)
        self.db.execute('''UPDATE bridge_subscriptions SET active=0 WHERE expires<=?
          OR session_id NOT IN (SELECT id FROM sessions WHERE ended IS NULL)''', (now,))
        self.db.execute('''UPDATE bridge_outbox SET state='expired',lease=NULL WHERE
          state IN ('pending','sending') AND ((state='pending' AND expires<=?) OR subscription_id NOT IN
          (SELECT id FROM bridge_subscriptions WHERE active=1))''', (now,))
        self.db.execute("UPDATE bridge_outbox SET state='pending',lease=NULL WHERE state='sending' AND lease_until<=?", (now,))
        self.db.execute("UPDATE bridge_outbox SET state='expired',lease=NULL WHERE state='pending' AND expires<=?", (now,))
        for sub in self.db.execute('SELECT id,policy FROM bridge_subscriptions WHERE active=1').fetchall():
            if quiet_status(validated_policy(json.loads(sub['policy'])), now)['active']:
                self.db.execute("UPDATE bridge_outbox SET state='suppressed',lease=NULL WHERE subscription_id=? AND state IN ('pending','sending')", (sub['id'],))

    def observations(self, session_id, device, end, policy, focus=None, channels=None):
        window = max(10, policy['long_press_ms']/1000 + policy['tap_gap_ms']/1000)
        params = [session_id, device, end-window, end]
        where = 'session_id=? AND device=? AND at>=? AND at<=?'
        if channels:
            where += " AND json_extract(payload,'$.channel') IN ("+','.join('?' for _ in channels)+')'
            params.extend(channels)
        rows = self.db.execute('SELECT * FROM events WHERE '+where+' ORDER BY at DESC,id DESC LIMIT 201',params).fetchall()
        values = [dict(json.loads(r['payload']), id=r['id'], device=r['device'], boot=r['boot'], at=r['at']) for r in reversed(rows[:200])]
        result = pressure_observations(values, policy, focus)
        result.update(context_window_seconds=window, truncated=len(rows)>200)
        return result

    @staticmethod
    def public_subscription(row):
        return {k: row[k] for k in ['id', 'target_id', 'session_id', 'device_id', 'transport', 'created', 'expires', 'active']}

    def subscribe(self, owner, target_id, session_id, device_id, transport='stream', ttl_sec=300,
                  policy=None, feedback=None, subscription_id=None, callback=None, secret=None, arguments=None,
                  now=None):
        now = time.time() if now is None else now
        text(owner, 'owner'); text(target_id, 'target_id', 256)
        text(session_id, 'session_id'); text(device_id, 'device_id')
        if transport not in ('stream', 'webhook') or type(ttl_sec) not in (int, float) or not math.isfinite(ttl_sec) or not 1 <= ttl_sec <= 3600:
            raise ValueError('Invalid transport or ttl_sec (1..3600)')
        prefs = self.preferences()
        policy = validated_policy(prefs['policy'] if policy is None else policy)
        feedback = validated_feedback(prefs['feedback'] if feedback is None else feedback)
        identity = json.dumps([owner,target_id,session_id,device_id,transport],ensure_ascii=False,separators=(',',':'))
        sid = subscription_id or 'sub_'+hashlib.sha256(identity.encode()).hexdigest()
        with self.lock, self.db:
            self._expire(now)
            session = self.db.execute('SELECT * FROM sessions WHERE id=? AND ended IS NULL', (session_id,)).fetchone()
            if not session:
                raise ValueError('Start an active interaction session before subscribing')
            previous = self.db.execute('SELECT * FROM bridge_subscriptions WHERE id=?', (sid,)).fetchone()
            if previous and previous['owner'] != owner:
                raise ValueError('Subscription belongs to another owner')
            active = self.db.execute('SELECT * FROM bridge_subscriptions WHERE active=1 AND id<>?', (sid,)).fetchone()
            if active:
                raise ValueError('An active reply target already exists; explicitly unsubscribe it first')
            if previous and (previous['target_id'] != target_id or previous['session_id'] != session_id):
                raise ValueError('Subscription identity cannot change reply target or session')
            self.db.execute('''INSERT INTO bridge_subscriptions
              (id,owner,target_id,session_id,device_id,transport,created,expires,active,policy,feedback,callback,secret,arguments)
              VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              expires=excluded.expires,active=1,policy=excluded.policy,feedback=excluded.feedback,
              callback=excluded.callback,secret=excluded.secret,arguments=excluded.arguments''',
              (sid, owner, target_id, session_id, device_id, transport, previous['created'] if previous else now,
               now+ttl_sec, json.dumps(policy), json.dumps(feedback, ensure_ascii=False), callback, secret,
               json.dumps(arguments or {}, sort_keys=True, separators=(',', ':'))))
            return self.public_subscription(self.db.execute('SELECT * FROM bridge_subscriptions WHERE id=?', (sid,)).fetchone())

    def unsubscribe(self, owner, subscription_id, now=None):
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM bridge_subscriptions WHERE id=?', (subscription_id,)).fetchone()
            if row and row['owner'] != owner:
                raise ValueError('Subscription belongs to another owner')
            self.db.execute('UPDATE bridge_subscriptions SET active=0 WHERE id=?', (subscription_id,))
            self.db.execute("UPDATE bridge_outbox SET state='cancelled',lease=NULL WHERE subscription_id=? AND state IN ('pending','sending')", (subscription_id,))
        return dict(unsubscribed=True)

    def enqueue(self, row_id, device, at, session_id, event, now):
        # Called while Companion owns the archive transaction. No network I/O here.
        if event.get('direction', 'input') != 'input':
            return
        kind = event.get('sensor_type', 'pressure')
        if kind not in ('pressure', 'temperature') or (kind == 'pressure' and event.get('phase') not in ('start','end')):
            return
        if kind == 'pressure' and (event.get('quality','ok') != 'ok' or event.get('source') not in ('sensor','simulation')):
            return
        for sub in self.db.execute('SELECT * FROM bridge_subscriptions WHERE active=1 AND session_id=? AND device_id=?', (session_id, device)).fetchall():
            policy = validated_policy(json.loads(sub['policy']))
            if sub['expires'] <= now or at < sub['created'] or now-at > policy['max_age_sec'] or at-now > 2:
                continue
            if event.get('source') == 'simulation' and not policy['allow_simulation']:
                continue
            if quiet_status(policy, now)['active'] or quiet_status(policy, at)['active']:
                continue
            if kind == 'pressure' and event.get('phase') == 'end':
                if not policy['notify_pressure_patterns']:
                    continue
                observed = self.observations(session_id, device, at, policy, {row_id})
                if not any(o['kind'] in ('completed_long_press', 'repeated_short_presses') for o in observed['observations']):
                    continue
            if kind == 'temperature':
                value = event.get('value')
                baseline = self.db.execute('SELECT value FROM bridge_temperature_baselines WHERE subscription_id=? AND channel=?', (sub['id'],event.get('channel'))).fetchone()
                if (not policy['temperature_enabled'] or event.get('quality') != 'ok' or
                    type(value) not in (int, float) or not math.isfinite(value) or
                    (baseline is not None and abs(value-baseline['value']) < policy['temperature_delta_c'])):
                    continue
            inserted = self.db.execute('INSERT OR IGNORE INTO bridge_seen VALUES(?,?)', (sub['id'], row_id)).rowcount
            if not inserted:
                continue
            snapshot = dict(event, sensor_type=kind, direction='input', at=at, device_id=device, archive_event_id=row_id)
            args = json.loads(sub['arguments'])
            if args.get('channels') and event.get('channel') not in args['channels']:
                continue
            pending = self.db.execute('''SELECT * FROM bridge_outbox WHERE subscription_id=? AND state='pending'
              AND attempts=0 AND created+?>? ORDER BY id DESC LIMIT 1''',
              (sub['id'], policy['merge_ms']/1000, now)).fetchone()
            if pending and len(json.loads(pending['payload'])['data']['events']) < 16:
                payload = json.loads(pending['payload']); payload['data']['events'].append(snapshot)
                self.db.execute('UPDATE bridge_outbox SET payload=? WHERE id=?', (json.dumps(payload, ensure_ascii=False), pending['id']))
            else:
                ready = max(now+policy['merge_ms']/1000, sub['next_allowed'])
                if ready >= min(sub['expires'], at+policy['max_age_sec']):
                    continue
                payload = dict(eventId='evt_'+uuid.uuid4().hex, name='doll.interaction',
                    timestamp=dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat(), cursor=None,
                    data=dict(device_id=device, session_id=session_id, events=[snapshot],
                              feedback=json.loads(sub['feedback']), persona=self.c.setting('persona')))
                self.db.execute('''INSERT INTO bridge_outbox
                  (event_id,subscription_id,payload,created,ready,expires,state) VALUES(?,?,?,?,?,?,'pending')''',
                  (payload['eventId'], sub['id'], json.dumps(payload, ensure_ascii=False), now, ready,
                   min(sub['expires'], at+policy['max_age_sec'])))
                self.db.execute('UPDATE bridge_subscriptions SET next_allowed=? WHERE id=?',
                                (ready+policy['cooldown_ms']/1000, sub['id']))
            if kind == 'temperature':
                self.db.execute('INSERT OR REPLACE INTO bridge_temperature_baselines VALUES(?,?,?)', (sub['id'],event['channel'],event['value']))

    def claim(self, owner=None, subscription_id=None, transport='stream', now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            self._expire(now)
            where = ["o.state='pending'", 'o.ready<=?', 's.active=1', 's.transport=?']
            params = [now, transport]
            if owner is not None: where.append('s.owner=?'); params.append(owner)
            if subscription_id is not None: where.append('s.id=?'); params.append(subscription_id)
            # Only one unacknowledged delivery per target prevents concurrent model calls.
            where.append("NOT EXISTS(SELECT 1 FROM bridge_outbox busy WHERE busy.subscription_id=s.id AND busy.state='sending')")
            row = self.db.execute('''SELECT o.*,s.owner,s.target_id,s.callback,s.secret FROM bridge_outbox o
              JOIN bridge_subscriptions s ON s.id=o.subscription_id WHERE '''+' AND '.join(where)+' ORDER BY o.id LIMIT 1', params).fetchone()
            if not row:
                return None
            payload = json.loads(row['payload'])
            if row['attempts'] == 0:
                sub = self.db.execute('SELECT * FROM bridge_subscriptions WHERE id=?', (row['subscription_id'],)).fetchone()
                policy = validated_policy(json.loads(sub['policy']))
                selected = {e['archive_event_id'] for e in payload['data']['events'] if 'archive_event_id' in e}
                allowed = json.loads(sub['arguments']).get('channels')
                summary = self.observations(sub['session_id'], sub['device_id'],
                    max(e['at'] for e in payload['data']['events']), policy, selected, allowed)
                payload['data']['summary'] = summary
                payload['data']['feedback'] = validated_feedback(json.loads(sub['feedback']))
                self.db.execute('UPDATE bridge_outbox SET payload=? WHERE id=?', (json.dumps(payload,ensure_ascii=False),row['id']))
            lease = secrets.token_hex(24)
            # Stream consumers renew this lease during model generation.
            self.db.execute("UPDATE bridge_outbox SET state='sending',lease=?,lease_until=?,attempts=attempts+1 WHERE id=?", (lease, now+15, row['id']))
            return dict(row, lease=lease, payload=payload, attempts=row['attempts']+1)

    def renew(self, owner, subscription_id, event_id, lease, now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            self._expire(now)
            changed = self.db.execute('''UPDATE bridge_outbox SET lease_until=? WHERE event_id=?
              AND subscription_id=? AND lease=? AND state='sending' AND subscription_id IN
              (SELECT id FROM bridge_subscriptions WHERE owner=? AND active=1)''', (now+15, event_id, subscription_id, lease, owner)).rowcount
            if not changed: raise ValueError('Expired or invalid delivery lease')
        return dict(renewed=True)

    def acknowledge(self, owner, subscription_id, event_id, lease, reply=None, source='model', now=None):
        now = time.time() if now is None else now
        if reply is not None:
            text(reply, 'reply', 8000)
            if source not in ('model', 'demo'): raise ValueError('Invalid reply source')
        with self.lock, self.db:
            self._expire(now)
            row = self.db.execute('''SELECT o.*,s.owner FROM bridge_outbox o JOIN bridge_subscriptions s
              ON s.id=o.subscription_id WHERE o.event_id=? AND s.id=?''', (event_id, subscription_id)).fetchone()
            if not row or row['owner'] != owner or row['lease'] != lease:
                raise ValueError('Invalid delivery ownership or lease')
            if row['state'] == 'delivered': return dict(acknowledged=True, duplicate=True)
            if row['state'] != 'sending': raise ValueError('Delivery expired or cancelled')
            self.db.execute("UPDATE bridge_outbox SET state='delivered',delivered=?,last_error=NULL WHERE id=?", (now, row['id']))
            if reply is not None:
                self.db.execute('INSERT OR IGNORE INTO bridge_replies(event_id,subscription_id,text,source,created) VALUES(?,?,?,?,?)',
                                (event_id, subscription_id, reply, source, now))
        return dict(acknowledged=True, duplicate=False)

    def finish_webhook(self, delivery, status, now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM bridge_outbox WHERE id=? AND lease=? AND state=\'sending\'', (delivery['id'], delivery['lease'])).fetchone()
            if not row: return
            self._expire(now)
            if 200 <= status < 300:
                self.db.execute("UPDATE bridge_outbox SET state='delivered',delivered=?,last_error=NULL WHERE id=? AND state='sending'", (now, row['id']))
            elif status in (410, 413) or (300 <= status < 500 and status not in (408, 429)) or row['attempts'] >= 5:
                self.db.execute("UPDATE bridge_outbox SET state='failed',last_error=? WHERE id=? AND state='sending'", ('http_'+str(status), row['id']))
                if status == 410:
                    self.db.execute('UPDATE bridge_subscriptions SET active=0 WHERE id=?', (row['subscription_id'],))
                    self._expire(now)
            else:
                self.db.execute("UPDATE bridge_outbox SET state='pending',lease=NULL,ready=?,last_error=? WHERE id=? AND state='sending'",
                                (now+min(16, 2**(row['attempts']-1)), 'http_'+str(status), row['id']))

    def state(self, owner='local-owner'):
        with self.lock, self.db:
            self._expire(time.time())
            subs = [self.public_subscription(r) for r in self.db.execute('SELECT * FROM bridge_subscriptions WHERE owner=? ORDER BY created DESC LIMIT 20', (owner,))]
            counts = dict((r['state'], r['n']) for r in self.db.execute('''SELECT o.state,COUNT(*) n FROM bridge_outbox o
              JOIN bridge_subscriptions s ON s.id=o.subscription_id WHERE s.owner=? GROUP BY o.state''', (owner,)))
            replies = [dict(r) for r in self.db.execute('''SELECT r.event_id,r.text,r.source,r.created FROM bridge_replies r
              JOIN bridge_subscriptions s ON s.id=r.subscription_id WHERE s.owner=? ORDER BY r.id DESC LIMIT 20''', (owner,))]
        preferences = self.preferences()
        return dict(version=VERSION, subscriptions=subs, deliveries=counts, replies=replies, preferences=preferences,
                    quiet_hours=quiet_status(preferences['policy'],time.time()))
