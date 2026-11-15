"""User-labelled combinations of overlapping pressure inputs; raw events stay intact."""
import math


def validate_rules(rules):
    if not isinstance(rules, list) or len(rules) > 16:
        raise ValueError('最多设置16个部位组合。')
    result = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {'name', 'channels', 'window_ms'}:
            raise ValueError('组合只支持 name、channels、window_ms。')
        name, channels, window = rule.get('name'), rule.get('channels'), rule.get('window_ms', 1500)
        if not isinstance(name, str) or not name.strip() or len(name) > 40:
            raise ValueError('组合名称应为1～40字。')
        if (not isinstance(channels, list) or not 2 <= len(channels) <= 8 or
                any(type(c) is not int or not 0 <= c <= 15 for c in channels) or len(set(channels)) != len(channels)):
            raise ValueError('每个组合选择2～8个不同通道。')
        if type(window) is not int or not 100 <= window <= 10000:
            raise ValueError('组合按下间隔应为100～10000毫秒。')
        item = dict(name=name.strip(), channels=sorted(channels), window_ms=window)
        if any(r['name'] == item['name'] or r['channels'] == item['channels'] for r in result):
            raise ValueError('组合名称与通道组合不能重复。')
        result.append(item)
    return result


def recognize(events, rules, selected=None):
    """Replay starts/releases in order. A match needs actual overlap, same boot/source."""
    active, matches = {}, []
    selected_ids = None if selected is None else {e.get('event_id', e.get('id')) for e in selected}
    rows = sorted((e for e in events if e.get('sensor_type', 'pressure') == 'pressure'
                   and e.get('quality') == 'ok' and e.get('source') in ('sensor', 'simulation') and e.get('direction', 'input') == 'input'
                   and e.get('delivery_quality', 'live') == 'live'
                   and type(e.get('at')) in (int, float) and math.isfinite(e['at'])), key=lambda e: (e['at'], e.get('id', 0)))
    for event in rows:
        scope = (event.get('device_id'), event.get('boot'), event.get('source'), event.get('session_id'))
        held = active.setdefault(scope, {})
        channel = event.get('channel')
        if event.get('phase') == 'end':
            if channel in held and held[channel].get('touch_id') == event.get('touch_id'):
                del held[channel]
            continue
        if event.get('phase') != 'start':
            continue
        for c, old in list(held.items()):
            end = old.get('ended_at')
            if end is not None and end <= event['at']:
                del held[c]
        held[channel] = event
        for rule in rules:
            if channel not in rule['channels'] or not all(c in held for c in rule['channels']):
                continue
            members = [held[c] for c in rule['channels']]
            if (event['at'] - min(e['at'] for e in members)) * 1000 > rule['window_ms']:
                continue
            ids = [e.get('event_id', e.get('id')) for e in members]
            if selected_ids is not None and event.get('event_id', event.get('id')) not in selected_ids:
                continue
            matches.append(dict(name=rule['name'], channels=rule['channels'], event_ids=ids,
                                trigger_event_id=event.get('event_id', event.get('id')),
                                at=event['at'], source=event.get('source'), interpretation='user_defined_combination'))
    return matches
