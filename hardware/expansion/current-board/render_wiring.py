"""Render a wiring reference from saved native pad coordinates; not a PCB export."""
from html import escape
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render():
    reference = json.loads((HERE / 'board-reference.json').read_text(encoding='utf-8'))
    components = {c['ref']: c for c in reference['components']}
    pads = {int(p['padNumber']): p for p in components['U1']['pads']}
    wires = [
        (15, 'GND', '#475569'), (16, 'SYS5V', '#d97706'),
        (10, 'TEMP · GPIO1', '#b45309'), (2, 'SDA · GPIO6', '#2563eb'),
        (3, 'SCL · GPIO7', '#0891b2'), (6, 'VIB · GPIO10', '#7c3aed'),
        (7, 'LIGHT · GPIO20', '#be185d'), (8, 'SWITCH · GPIO21', '#15803d'),
    ]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1180" viewBox="0 0 1600 1180">',
           '<rect width="1600" height="1180" fill="#f1f5f9"/>',
           '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;fill:#0f172a} .sub{fill:#475569} .tiny{font-size:15px} .small{font-size:18px}</style>']

    def text(x, y, value, size=20, fill=None, weight=None, anchor=None):
        extra = (f' style="fill:{fill}"' if fill else '')
        extra += f' font-weight="{weight}"' if weight else ''
        extra += f' text-anchor="{anchor}"' if anchor else ''
        svg.append(f'<text x="{x}" y="{y}" font-size="{size}"{extra}>{escape(value)}</text>')

    def rect(x, y, w, h, fill, stroke='#cbd5e1', radius=15):
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

    text(42, 58, '现板内测扩展 · 接线参考', 36, weight='700')
    text(42, 97, '适用：开关居中靠下的贴片版｜八路压力保持原样｜不切主板走线', 21, '#475569')
    rect(30, 130, 540, 830, '#ffffff')
    text(58, 171, '主板正面 · 天线上 / USB朝下', 24, weight='700')
    origin_x, origin_y, scale = 92, 208, 0.30

    def point(x, y):
        return origin_x + x * scale, origin_y + (1750 - y) * scale

    bx, by = point(0, 1750)
    rect(bx, by, 1350 * scale, 1750 * scale, '#e0f2fe', '#0369a1', 12)
    bb = components['U1']['bbox']
    mx, my = point(bb['minX'], bb['maxY'])
    rect(mx, my, (bb['maxX'] - bb['minX']) * scale,
         (bb['maxY'] - bb['minY']) * scale, '#e2e8f0', '#64748b', 5)
    text(295, 245, 'ANT', 19, '#475569', anchor='middle')
    text(295, 499, 'USB ↓', 19, '#475569', anchor='middle')
    colors = {pad: color for pad, _, color in wires}
    for number, p in pads.items():
        x, y = point(p['x'], p['y'])
        color = colors.get(number, '#64748b')
        rect(x - 10, y - 8, 20, 16, color, '#ffffff', 2)
        label = p['role'].split(' / ')[0]
        left = p['x'] < 675
        text(x + (17 if left else -17), y + 5, label, 15, color,
             anchor='start' if left else 'end')
    for ref in ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8']:
        c = components[ref]
        for p in c['pads']:
            x, y = point(p['x'], p['y'])
            svg.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#94a3b8" stroke="#fff"/>')
        x, y = point(c['x'], c['y'])
        text(x + (-18 if c['x'] < 675 else 18), y + 6,
             ref, 15, '#475569', anchor='end' if c['x'] < 675 else 'start')
    sx, sy = point(500, 209)
    rect(sx, sy, 350 * scale, 148 * scale, '#cbd5e1', '#475569', 5)
    text(295, sy + 28, 'SW1', 18, weight='700', anchor='middle')
    for p in components['SW1']['pads']:
        x, y = point(p['x'], p['y'])
        svg.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#475569"/>')
    text(59, 789, '以模块自身丝印和封装脚号双重核对', 19, weight='700')
    text(59, 827, '灰色焊点与八路压力保持原用途。', 18, '#475569')
    text(59, 862, '背面观察需翻转，不能直接照搬此图。', 18, '#475569')
    text(59, 901, 'SW1中脚与模块5V同属SYS5V。', 18, '#475569')
    rect(640, 190, 310, 500, '#ffffff')
    text(667, 228, '新增8P转接线束', 24, weight='700')
    for index, (number, label, color) in enumerate(wires):
        p = pads[number]
        x, y = point(p['x'], p['y'])
        ty = 274 + index * 50
        badge_x = x - 27 if p['x'] < 675 else x + 27
        svg.append(f'<circle cx="{badge_x}" cy="{y}" r="10" fill="{color}"/>')
        text(badge_x, y + 4, str(index + 1), 12, '#ffffff', '700', 'middle')
        svg.append(f'<circle cx="657" cy="{ty}" r="7" fill="{color}"/>')
        text(677, ty + 6, f'{index + 1}  {label}', 19, color, '700')
    text(663, 660, '按编号一一连接；不是原板插座', 16, '#475569')
    boxes = [
        (190, '两路独立稳压 / 公共地', 'SYS5V → 3V3_LOGIC；SYS5V → 3V3_MOTOR', '#d97706'),
        (322, '温度 · 1～2只 DS18B20', '3V3_LOGIC / GND / GPIO1，数据线上拉4.7kΩ', '#b45309'),
        (454, '姿态变化 · LIS3DH', '3V3_LOGIC / GND / GPIO6 SDA / GPIO7 SCL', '#2563eb'),
        (586, '振动 · ERM马达与驱动', 'GPIO10 → MOSFET；马达使用匹配的独立电源', '#7c3aed'),
        (718, '灯效 · 单颗低电流LED', 'GPIO20 → 1kΩ → LED → GND', '#be185d'),
        (850, '开关 · 一个无源干接点', 'GPIO21，上拉10kΩ；串联1kΩ，滤波100nF', '#15803d'),
    ]
    for y, title, detail, color in boxes:
        rect(1000, y, 560, 108, '#ffffff', color)
        text(1024, y + 40, title, 23, color, '700')
        text(1024, y + 77, detail, 17, '#475569')
    rect(640, 718, 310, 240, '#fff7ed', '#fdba74')
    text(662, 757, '装配边界', 23, '#9a3412', '700')
    for i, line in enumerate(['马达不接FSR口或GPIO电源', '两个稳压输出不互相并联', 'GPIO20/21与UART互斥', '扩展不挤入原电池仓', '需扩展候选软件，逐项接线核对']):
        text(662, 798 + i * 30, line, 16, '#9a3412')
    text(42, 1010, '仅为接线设计示意：按2026-10-17原生回读焊盘坐标绘制；未修改原PCB，不是制造图。', 19, '#475569')
    text(42, 1050, '扩展候选支持温度、姿态、振动、灯和开关；需同批软件，新增模块逐项接线验收。', 19, '#475569')
    text(42, 1090, '电源先断开再接线；正式装配保留原C9（1nF）及R17（1kΩ）；交叉线没有连接点时不相连。', 19, '#475569')
    text(42, 1132, '完整电路、器件规格、软件边界和安装步骤：同目录README / WIRING / SOFTWARE / ACCEPTANCE。', 18, '#64748b')
    svg.append('</svg>')
    path = HERE / 'wiring.svg'
    path.write_text('\n'.join(svg) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    print(render())
