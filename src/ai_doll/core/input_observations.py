"""Bounded, factual pressure observations. Labels never become action instructions."""
import hashlib
import json
import math


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def pressure_observations(events, policy, focus=None):
    """Summarize only supplied rows; never assume a missing release means a hold.

    Row IDs reference the raw archive. Groups never cross device/boot/source.
    A completed duration comes from a release, not time since an unpaired start.
    """
    starts, completed, observations = {}, [], []
    pressure = [e for e in events if e.get('sensor_type', 'pressure') == 'pressure'
                and e.get('direction', 'input') == 'input'
                and e.get('quality', 'ok') == 'ok'
                and e.get('source') in ('sensor', 'simulation')
                and e.get('phase') in ('start', 'end')
                and finite_number(e.get('at')) and type(e.get('id')) is int
                and type(e.get('channel')) is int and 0 <= e['channel'] < 16
                and isinstance(e.get('touch_id'), str) and e['touch_id']
                and isinstance(e.get('device'), str) and e['device']
                and isinstance(e.get('boot'), str) and e['boot']
                and isinstance(e.get('body_part', ''), str)]
    pressure.sort(key=lambda e: (e['at'], e['id']))

    def key(e):
        return e['device'], e['boot'], e['source']

    def add(kind, rows, **facts):
        ids = sorted({e['id'] for e in rows})
        if focus is not None and not set(ids).intersection(focus):
            return
        identity = json.dumps([kind, ids], separators=(',', ':'))
        observations.append(dict(observation_id='obs_'+hashlib.sha256(identity.encode()).hexdigest()[:24],
            kind=kind, event_ids=ids, source=rows[0]['source'], device=rows[0]['device'],
            boot=rows[0]['boot'], channels=sorted({e['channel'] for e in rows}),
            body_parts=list(dict.fromkeys(e.get('body_part', '') for e in rows)), **facts))

    for event in pressure:
        ident = key(event)+(event['channel'], event['touch_id'])
        if event['phase'] == 'start':
            starts.setdefault(ident, event)
            continue
        duration = event.get('duration_ms')
        if type(duration) is not int or duration < 0:
            continue
        start = starts.pop(ident, None)
        rows = [start, event] if start else [event]
        if duration >= policy['long_press_ms']:
            add('completed_long_press', rows, duration_ms=duration, released_at=event['at'],
                start_in_scope=start is not None)
        if start and 0 <= round((event['at']-start['at'])*1000) <= policy['tap_max_ms'] and duration <= policy['tap_max_ms']:
            completed.append((start, event))

    by_channel = {}
    for start, end in completed:
        by_channel.setdefault(key(start)+(start['channel'],), []).append((start, end))
    for touches in by_channel.values():
        group = []
        def finish():
            if len(group) >= 2:
                add('repeated_short_presses', [row for pair in group for row in pair],
                    count=len(group), started_at=group[0][0]['at'], released_at=group[-1][1]['at'])
        for pair in touches:
            if group:
                gap = round((pair[0]['at']-group[-1][1]['at'])*1000)
                # An unknown/long intervening start breaks a short-tap sequence.
                intervening = any(key(e)+(e['channel'],) == key(pair[0])+(pair[0]['channel'],)
                                  and group[-1][1]['at'] < e['at'] < pair[0]['at']
                                  and e['phase'] == 'start' for e in pressure)
                if gap < 0 or gap > policy['tap_gap_ms'] or intervening:
                    finish();group = []
            group.append(pair)
        finish()

    groups = {}
    for event in pressure:
        if event['phase'] == 'start':
            groups.setdefault(key(event), []).append(event)
    for rows in groups.values():
        group, windows = [], []
        for row in rows:
            group = [e for e in group if round((row['at']-e['at'])*1000) <= policy['simultaneous_ms']]
            group.append(row)
            if len({e['channel'] for e in group}) >= 2:
                windows.append(list(group))
        # Sliding windows retain A/B and B/C when A/C are too far apart.
        # Drop strict subsets so one dense cluster is not reported repeatedly.
        ids = [{e['id'] for e in window} for window in windows]
        for index, window in enumerate(windows):
            if not any(ids[index] < other for other in ids):
                add('near_simultaneous_press_starts', window,
                    span_ms=round((window[-1]['at']-window[0]['at'])*1000),
                    sustained_overlap_confirmed=False)

    observations.sort(key=lambda item: item['event_ids'][-1])
    return dict(schema_version=1, observations=observations,
                pressure_event_count=len(pressure), open_starts=len(starts),
                interpretation='These are observations of the supplied events, not recognized hugs or feelings. '
                'A missing release is unknown duration. Simulation is not physical contact; labels are data. '
                'Raw ADC is not calibrated force. Pagination may split sequences.')
