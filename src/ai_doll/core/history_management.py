"""Archive export, exact deletion previews, retention and factual statistics."""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import secrets
import time

ZONE=dt.timezone(dt.timedelta(hours=8))
FILTERS={'start_date','end_date','device','body_part','sensor_type','direction','source','session_id','time_scope'}


def validate_filters(filters=None):
    if filters is not None and not isinstance(filters,dict):raise ValueError('History filters must be an object')
    f=dict(filters or {})
    if set(f)-FILTERS:raise ValueError('Unknown history filter')
    for key in ('start_date','end_date'):
        if f.get(key) is not None:
            value=f[key]
            if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
                raise ValueError('Dates must use YYYY-MM-DD')
            day=dt.date.fromisoformat(value)
            if key=='end_date' and day==dt.date.max:raise ValueError('End date must allow the following exclusive day')
    if f.get('start_date') and f.get('end_date') and f['start_date']>f['end_date']:
        raise ValueError('Start date must not follow end date')
    for key in ('device','body_part','sensor_type','direction','source','session_id'):
        if f.get(key) is not None and (not isinstance(f[key],str) or not 1<=len(f[key])<=256):
            raise ValueError('History text filters must be nonempty text up to 256 characters')
    if f.get('direction') not in (None,'input','output'):raise ValueError('Invalid direction')
    if f.get('sensor_type') is not None and not re.fullmatch('[a-z][a-z0-9_]{0,47}',f['sensor_type']):
        raise ValueError('Invalid sensor type')
    f.setdefault('time_scope','all')
    if f['time_scope'] not in ('all','known','unknown'):raise ValueError('Invalid time scope')
    if f['time_scope']=='unknown' and (f.get('start_date') or f.get('end_date')):
        raise ValueError('Unknown timestamps cannot be filtered by occurrence date')
    return {k:v for k,v in f.items() if v is not None}


def clauses(f):
    dates=[];values=[]
    for key,op,extra in [('start_date','>=',0),('end_date','<',1)]:
        if f.get(key):
            day=dt.date.fromisoformat(f[key])+dt.timedelta(days=extra)
            dates.append('at'+op+'?');values.append(dt.datetime.combine(day,dt.time.min,ZONE).timestamp())
    if f['time_scope']=='unknown':where=['at IS NULL']
    elif f['time_scope']=='known':where=['at IS NOT NULL']+dates
    elif dates:where=['(('+ ' AND '.join(dates)+') OR at IS NULL)']
    else:where=[]
    for key in ('device','session_id'):
        if key in f:where.append(key+'=?');values.append(f[key])
    for key in ('body_part','sensor_type','direction','source'):
        if key in f:
            expr="json_extract(payload,'$."+key+"')"
            if key=='sensor_type':expr="COALESCE("+expr+",'pressure')"
            if key=='direction':expr="COALESCE("+expr+",'input')"
            where.append(expr+'=?');values.append(f[key])
    return ' AND '.join(where) or '1',values


def public_event(row):
    value=json.loads(row['payload'])
    value.setdefault('time_quality','legacy_estimate')
    value.setdefault('sensor_type','pressure');value.setdefault('direction','input')
    return dict(value,id=row['id'],device=row['device'],boot_id=row['boot'],at=row['at'],session_id=row['session_id'])


class HistoryManager:
    def __init__(self,companion):
        self.c=companion;self.db=companion.db;self.lock=companion.lock
        self.previews={};self.last_maintenance=0
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS deleted_events(device TEXT,boot TEXT,seq INTEGER,
            PRIMARY KEY(device,boot,seq));
          CREATE TABLE IF NOT EXISTS deleted_touches(device TEXT,touch_id TEXT,
            PRIMARY KEY(device,touch_id));
          CREATE INDEX IF NOT EXISTS history_time ON events(at,id);
          CREATE INDEX IF NOT EXISTS history_session ON events(session_id,id);
        ''')

    def export(self,filters=None,format='json',after=0,limit=200,max_id=None):
        f=validate_filters(filters)
        if format not in ('json','csv'):raise ValueError('Export format must be json or csv')
        if type(after) is not int or not 0<=after<=9223372036854775807 or type(limit) is not int or not 1<=limit<=500:
            raise ValueError('after >= 0 and limit 1..500 required')
        if max_id is not None and (type(max_id) is not int or not 0<=max_id<=9223372036854775807):raise ValueError('Invalid upper archive ID')
        where,args=clauses(f)
        with self.lock:
            upper=self.db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0] if max_id is None else max_id
            rows=self.db.execute('SELECT * FROM events WHERE '+where+' AND id>? AND id<=? ORDER BY id LIMIT ?',args+[after,upper,limit+1]).fetchall()
        records=[public_event(r) for r in rows[:limit]]
        result=dict(schema_version=1,format=format,timezone='Asia/Shanghai',filters=f,max_id=upper,
                    next_cursor=records[-1]['id'] if records else after,has_more=len(rows)>limit,count=len(records))
        if format=='json':result['records']=records
        else:
            stream=io.StringIO(newline='');writer=csv.writer(stream)
            fields=['id','device','boot_id','seq','at','time_quality','session_id','channel','body_part','sensor_type','direction','phase','source','value','unit','duration_ms','payload_json']
            writer.writerow(fields)
            for record in records:
                cells=[]
                for key in fields:
                    value=json.dumps(record,ensure_ascii=False,separators=(',',':')) if key=='payload_json' else record.get(key)
                    if isinstance(value,str) and value.lstrip(' \t\r\n').startswith(('=','+','-','@')):value="'"+value
                    cells.append('' if value is None else value)
                writer.writerow(cells)
            result['content']=stream.getvalue();result['spreadsheet_text_escaped']=True
        result['consistency']='Upper archive ID is fixed across pages; concurrent deletion may remove rows.'
        return result

    def _selection(self,filters,upper=None,cutoff=None,include_unknown=False):
        # All callers hold the archive lock. Temporary tables are connection-local.
        for statement in ('DROP TABLE IF EXISTS temp.history_selected','DROP TABLE IF EXISTS temp.history_touches',
                'CREATE TEMP TABLE history_selected(id INTEGER PRIMARY KEY)',
                'CREATE TEMP TABLE history_touches(device TEXT,touch_id TEXT,PRIMARY KEY(device,touch_id))'):
            self.db.execute(statement)
        if cutoff is None:
            where,args=clauses(filters)
            self.db.execute('INSERT INTO history_selected SELECT id FROM events WHERE '+where+' AND id<=?',args+[upper])
        else:
            where='at<?';args=[cutoff]
            if include_unknown:
                where+=" OR (at IS NULL AND json_type(payload,'$.received_at') IN ('integer','real') AND json_extract(payload,'$.received_at')<?)";args.append(cutoff)
            self.db.execute('INSERT INTO history_selected SELECT id FROM events WHERE ('+where+') '
                'AND (session_id IS NULL OR session_id NOT IN (SELECT id FROM sessions WHERE ended IS NULL))',args)
        initial=self.db.execute('SELECT COUNT(*) FROM history_selected').fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO history_touches SELECT device,json_extract(payload,'$.touch_id') FROM events "
            "WHERE id IN (SELECT id FROM history_selected) AND COALESCE(json_extract(payload,'$.sensor_type'),'pressure')='pressure' "
            "AND json_type(payload,'$.touch_id')='text'")
        if cutoff is not None:
            # A pressure gesture survives until ALL its archived pieces are old.
            self.db.execute("DELETE FROM history_touches WHERE EXISTS (SELECT 1 FROM events e WHERE e.device=history_touches.device "
                "AND json_extract(e.payload,'$.touch_id')=history_touches.touch_id AND "
                "(e.at>=? OR (e.at IS NULL AND (?=0 OR json_type(e.payload,'$.received_at') NOT IN ('integer','real') "
                "OR json_extract(e.payload,'$.received_at') IS NULL OR json_extract(e.payload,'$.received_at')>=?)) "
                "OR e.session_id IN (SELECT id FROM sessions WHERE ended IS NULL)))",(cutoff,int(include_unknown),cutoff))
            self.db.execute("DELETE FROM history_selected WHERE id IN (SELECT e.id FROM events e WHERE "
                "COALESCE(json_extract(e.payload,'$.sensor_type'),'pressure')='pressure' AND json_type(e.payload,'$.touch_id')='text' "
                "AND NOT EXISTS (SELECT 1 FROM history_touches t WHERE t.device=e.device AND t.touch_id=json_extract(e.payload,'$.touch_id')))")
            initial=self.db.execute('SELECT COUNT(*) FROM history_selected').fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO history_selected SELECT e.id FROM events e JOIN history_touches t "
            "ON t.device=e.device AND t.touch_id=json_extract(e.payload,'$.touch_id') "
            "WHERE COALESCE(json_extract(e.payload,'$.sensor_type'),'pressure')='pressure'")
        active=self.db.execute('SELECT COUNT(*) FROM events WHERE id IN (SELECT id FROM history_selected) '
            'AND session_id IN (SELECT id FROM sessions WHERE ended IS NULL)').fetchone()[0]
        if active:raise ValueError('End the affected interaction before deleting its history')
        counts=self.db.execute('SELECT COUNT(*) n,SUM(at IS NULL) unknown,MIN(at) first,MAX(at) last FROM events '
            'WHERE id IN (SELECT id FROM history_selected)').fetchone()
        related="subscription_id IN (SELECT id FROM bridge_subscriptions WHERE session_id IN (SELECT session_id FROM events WHERE id IN (SELECT id FROM history_selected)))"
        deliveries=self.db.execute('SELECT COUNT(*) FROM bridge_outbox WHERE '+related).fetchone()[0]
        replies=self.db.execute('SELECT COUNT(*) FROM bridge_replies WHERE '+related).fetchone()[0]
        digest=hashlib.sha256()
        for row in self.db.execute('SELECT * FROM events WHERE id IN (SELECT id FROM history_selected) ORDER BY id'):
            digest.update(json.dumps(dict(row),sort_keys=True,ensure_ascii=False).encode())
        for row in self.db.execute('SELECT * FROM touches WHERE EXISTS (SELECT 1 FROM history_touches t WHERE t.device=touches.device AND t.touch_id=touches.touch_id) ORDER BY id'):
            digest.update(json.dumps(dict(row),sort_keys=True,ensure_ascii=False).encode())
        for table in ('bridge_outbox','bridge_replies'):
            for row in self.db.execute('SELECT * FROM '+table+' WHERE '+related+' ORDER BY id'):
                digest.update(json.dumps(dict(row),sort_keys=True,ensure_ascii=False).encode())
        return dict(events=counts['n'],matched_events=initial,expanded_events=max(0,counts['n']-initial),
                    pressure_gestures=self.db.execute('SELECT COUNT(*) FROM history_touches').fetchone()[0],
                    unknown_time_events=counts['unknown'] or 0,first_at=counts['first'],last_at=counts['last'],
                    related_deliveries=deliveries,related_replies=replies),digest.hexdigest()

    def preview_delete(self,filters=None,all_records=False):
        f=validate_filters(filters)
        if type(all_records) is not bool:raise ValueError('all_records must be boolean')
        if not any(k!='time_scope' for k in f) and not all_records:
            raise ValueError('An unbounded deletion requires explicit all_records scope')
        with self.lock,self.db:
            now=time.time();self.previews={k:v for k,v in self.previews.items() if v['expires']>now}
            if len(self.previews)>=16:raise ValueError('Too many live deletion previews; wait two minutes')
            upper=self.db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
            counts,digest=self._selection(f,upper)
            token=secrets.token_urlsafe(32)
            self.previews[token]=dict(filters=f,upper=upper,digest=digest,expires=now+120)
            return dict(preview_token=token,expires_at=now+120,filters=f,counts=counts,
                note='Pressure gestures expand to all their recorded phases; associated session deliveries/replies are removed. New unrelated events are excluded.')

    def delete(self,preview_token,confirmed=False):
        if confirmed is not True:raise ValueError('Explicit user confirmation is required')
        if not isinstance(preview_token,str):raise ValueError('Invalid deletion preview')
        with self.lock,self.db:
            preview=self.previews.pop(preview_token,None)
            if not preview or preview['expires']<=time.time():raise ValueError('Preview expired or already used; preview again')
            counts,digest=self._selection(preview['filters'],preview['upper'])
            if digest!=preview['digest']:raise ValueError('Affected history changed; preview again')
            self._erase()
            return dict(deleted=True,counts=counts,preserved=['persona','channel configuration','feedback preferences','deduplication identifiers'])

    def _erase(self):
        self.db.execute('INSERT OR IGNORE INTO deleted_events SELECT device,boot,seq FROM events WHERE id IN (SELECT id FROM history_selected)')
        self.db.execute('INSERT OR IGNORE INTO deleted_touches SELECT * FROM history_touches')
        self.db.execute('DROP TABLE IF EXISTS temp.history_sessions')
        self.db.execute('CREATE TEMP TABLE history_sessions(id TEXT PRIMARY KEY)')
        self.db.execute('INSERT OR IGNORE INTO history_sessions SELECT session_id FROM events WHERE id IN (SELECT id FROM history_selected) AND session_id IS NOT NULL')
        related='subscription_id IN (SELECT id FROM bridge_subscriptions WHERE session_id IN (SELECT id FROM history_sessions))'
        self.db.execute('DELETE FROM bridge_replies WHERE '+related)
        self.db.execute('DELETE FROM bridge_outbox WHERE '+related)
        self.db.execute('DELETE FROM bridge_seen WHERE event_row IN (SELECT id FROM history_selected)')
        self.db.execute('DELETE FROM bridge_temperature_baselines WHERE '+related)
        self.db.execute('DELETE FROM touches WHERE EXISTS (SELECT 1 FROM history_touches t WHERE t.device=touches.device AND t.touch_id=touches.touch_id)')
        self.db.execute('DELETE FROM events WHERE id IN (SELECT id FROM history_selected)')
        self.db.execute('DELETE FROM history_sessions WHERE id IN (SELECT session_id FROM events WHERE session_id IS NOT NULL) '
            'OR id IN (SELECT session_id FROM touches WHERE session_id IS NOT NULL)')
        self.db.execute('DELETE FROM bridge_seen WHERE subscription_id IN (SELECT id FROM bridge_subscriptions WHERE session_id IN (SELECT id FROM history_sessions))')
        self.db.execute('DELETE FROM bridge_subscriptions WHERE session_id IN (SELECT id FROM history_sessions)')
        self.db.execute('DELETE FROM session_boundaries WHERE session_id IN (SELECT id FROM history_sessions)')
        self.db.execute('DELETE FROM sessions WHERE id IN (SELECT id FROM history_sessions) AND ended IS NOT NULL')

    def retention(self):
        value=json.loads(self.c.setting('history_retention','{}'))
        return dict(enabled=value.get('enabled',False),days=value.get('days',90),include_unknown=value.get('include_unknown',False),
                    last_run=json.loads(self.c.setting('history_retention_last_run','null')),
                    maintenance_error=getattr(self.c,'maintenance_error',None))

    @staticmethod
    def _policy(days,include_unknown):
        if type(days) is not int or not 1<=days<=3650:raise ValueError('Retention days must be 1..3650')
        if type(include_unknown) is not bool:raise ValueError('include_unknown must be boolean')

    def preview_retention(self,days=90,include_unknown=False):
        self._policy(days,include_unknown)
        with self.lock,self.db:
            cutoff=time.time()-days*86400
            counts,_=self._selection({},cutoff=cutoff,include_unknown=include_unknown)
            return dict(days=days,include_unknown=include_unknown,cutoff=cutoff,counts=counts,
                        note='Old pressure gestures with a newer phase and active interaction history are retained. Unknown time uses reception age only when explicitly enabled.')

    def set_retention(self,enabled,days=90,include_unknown=False,confirmed=False):
        self._policy(days,include_unknown)
        if type(enabled) is not bool or type(confirmed) is not bool:raise ValueError('Policy switches must be boolean')
        if enabled and not confirmed:raise ValueError('Explicit confirmation required before enabling automatic deletion')
        with self.lock:
            self.c.set_setting('history_retention',json.dumps(dict(enabled=enabled,days=days,include_unknown=include_unknown)))
            self.last_maintenance=0
            return self.retention()

    def maintain(self,now=None):
        now=time.time() if now is None else now
        with self.lock,self.db:
            policy=self.retention()
            if not policy['enabled'] or now-self.last_maintenance<3600:return
            counts,_=self._selection({},cutoff=now-policy['days']*86400,include_unknown=policy['include_unknown'])
            self._erase()
            self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('history_retention_last_run',json.dumps(dict(at=now,counts=counts))))
            self.last_maintenance=now

    def statistics(self,filters=None):
        f=validate_filters(filters);where,args=clauses(f)
        with self.lock:
            total=self.db.execute('SELECT COUNT(*) events,SUM(at IS NULL) unknown,MIN(at) first_at,MAX(at) last_at FROM events WHERE '+where,args).fetchone()
            def group(expr):
                return [dict(label=r[0],events=r[1]) for r in self.db.execute('SELECT '+expr+',COUNT(*) FROM events WHERE '+where+' GROUP BY '+expr+' ORDER BY COUNT(*) DESC LIMIT 100',args)]
            starts="COALESCE(json_extract(payload,'$.sensor_type'),'pressure')='pressure' AND json_extract(payload,'$.phase')='start'"
            presses=self.db.execute('SELECT COUNT(*) FROM events WHERE '+where+' AND '+starts,args).fetchone()[0]
            touch_where="EXISTS (SELECT 1 FROM events e WHERE e.device=touches.device AND json_extract(e.payload,'$.touch_id')=touches.touch_id AND e.id IN (SELECT id FROM events WHERE "+where+' AND '+starts+'))'
            duration=self.db.execute('SELECT COUNT(*) completed,COALESCE(SUM(duration_ms),0) duration_ms,AVG(duration_ms) average_duration_ms FROM touches WHERE duration_ms IS NOT NULL AND '+touch_where,args).fetchone()
            daily=[dict(date=r[0],events=r[1]) for r in self.db.execute("SELECT date(at,'unixepoch','+8 hours'),COUNT(*) FROM events WHERE ("+where+") AND at IS NOT NULL GROUP BY 1 ORDER BY 1 DESC LIMIT 366",args)]
            return dict(filters=f,timezone='Asia/Shanghai',**dict(total),unknown_time_events=total['unknown'] or 0,
                        pressure_starts=presses,**dict(duration),by_type=group("COALESCE(json_extract(payload,'$.sensor_type'),'pressure')"),
                        by_body_part=group("json_extract(payload,'$.body_part')"),by_source=group("json_extract(payload,'$.source')"),
                        by_time_quality=group("COALESCE(json_extract(payload,'$.time_quality'),'legacy_estimate')"),daily=daily,
                        group_limit=100,daily_limit=366,interpretation='Counts of archived events; pressure counts starts, durations use completed gestures whose start is in scope. Output is a command, not measured feedback. Unknown times never appear in daily counts; no inferred hugs.')
