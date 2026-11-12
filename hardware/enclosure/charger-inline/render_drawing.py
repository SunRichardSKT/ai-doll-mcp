"""Generate a dimension sheet from the same parameters as the CAD model."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run():
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    c,m,led=p['case'],p['module'],p['led_window']; W,L,H=c['width'],c['length'],c['height']; k=8
    x,y=100,145; px=(W-m['width'])/2
    pieces=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="720" viewBox="0 0 1100 720"><defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="none" stroke="#536b5a"/></marker></defs><style>text{{font-family:Segoe UI,Microsoft YaHei,sans-serif;fill:#304739}}.d{{stroke:#536b5a;stroke-width:1;fill:none;marker-start:url(#a);marker-end:url(#a)}}.label{{font-size:15px}}.small{{font-size:13px;fill:#65765f}}</style><rect width="1100" height="720" fill="#f7f8f3"/><text x="50" y="48" font-size="26" font-weight="600">充电模块四线保护壳 · CHARGER-P03</text><text x="50" y="80" class="small">双片卡扣 / 无五金件 / 长{L:g} × 宽{W:g} × 高{H:g} mm / 单位 mm</text>
<rect x="{x}" y="{y}" width="{W*k}" height="{L*k}" rx="24" fill="#dbe4d8" stroke="#607b65" stroke-width="2"/>
<rect x="{x+px*k}" y="{y+m['front_y']*k}" width="{m['width']*k}" height="{m['length']*k}" rx="3" fill="none" stroke="#748b8b" stroke-dasharray="5 4"/>
<rect x="{x+(W-led['width'])*k/2}" y="{y+(led['center_y']-led['length']/2)*k}" width="{led['width']*k}" height="{led['length']*k}" rx="5" fill="#91a99b" stroke="#536c5b"/>
<text x="{x+W*k/2}" y="{y+led['center_y']*k+5}" text-anchor="middle" font-size="15">灯窗 {led['width']:g}×{led['length']:g}</text>
<path d="M{x} {y-25} H{x+W*k}" class="d"/><text x="{x+W*k/2}" y="{y-34}" text-anchor="middle" class="label">{W:g}</text>
<path d="M{x-27} {y} V{y+L*k}" class="d"/><text x="{x-38}" y="{y+L*k/2}" transform="rotate(-90 {x-38} {y+L*k/2})" text-anchor="middle" class="label">{L:g}</text>''']
    ch=p['side_wire_channels']
    for xx in [ch['left_center_x'],W-ch['left_center_x']]:
        pieces.append(f'<rect x="{x+(xx-ch["width"]/2)*k}" y="{y+ch["front_y"]*k}" width="{ch["width"]*k}" height="{(ch["rear_y"]-ch["front_y"])*k}" fill="#719a9e" fill-opacity=".28" stroke="#719a9e" stroke-dasharray="4 3"/>')
    for xx in [6,9,12]:pieces.append(f'<rect x="{x+xx*k}" y="{y+14*k}" width="8" height="24" fill="#8a9d88"/>')
    for g in p['wire_groups']:
        cx=sum(g['centers_x'])/2
        pieces.append(f'<text x="{x+cx*k}" y="{y+29*k}" text-anchor="middle" font-size="13">{g["label"]}</text>')
    for i,xx in enumerate(p['wires']['centers_x']):
        pieces.append(f'<path d="M{x+xx*k} {y+L*k} v28" stroke="{chr(35)+("bb5247" if i%2==0 else "3e4c4e")}" stroke-width="9"/>')
    pieces.append(f'''<text x="{x+W*k/2}" y="{y+L*k+60}" text-anchor="middle" class="label">俯视 · 两侧蓝区为取电线通道</text>
<text x="405" y="153" class="label">侧向剖面示意</text>
<rect x="405" y="185" width="{L*k}" height="{H*k}" rx="10" fill="#c5d4c3" stroke="#607b65" stroke-width="2"/>
<rect x="{405+c['wall']*k}" y="{185+c['lid']*k}" width="{(L-2*c['wall'])*k}" height="{(H-c['floor']-c['lid'])*k}" fill="#f7f8f3"/>
<rect x="{405+m['front_y']*k}" y="{185+(H-m['bottom_z']-m['total_height'])*k}" width="{m['length']*k}" height="{m['total_height']*k}" fill="#7a9290"/>
<rect x="{405+24*k}" y="{185+c['lid']*k}" width="{8*k}" height="{(H-c['lid']-4.55)*k}" fill="#ccd6c6" stroke="#607b65"/>
<rect x="{405+24*k}" y="{185+(H-4.5)*k}" width="{8*k}" height="{(4.5-c['floor'])*k}" fill="#bacdb5" stroke="#607b65"/>
<path d="M{405+18*k} {185+(H-4.5)*k} H{405+(L+5)*k}" stroke="#bd594b" stroke-width="7" fill="none"/>
<path d="M{405+L*k+30} 185 V{185+H*k}" class="d"/><text x="{405+L*k+48}" y="{185+H*k/2+5}" class="label">{H:g}</text>
<text x="418" y="315" class="small">模块支承</text><text x="565" y="315" class="small">留线余量</text><text x="635" y="338" class="small">合盖夹线</text>
<text x="405" y="395" class="label">USB-C前孔</text>
<rect x="405" y="416" width="{W*k}" height="{H*k}" rx="24" fill="#dbe4d8" stroke="#607b65" stroke-width="2"/>
<rect x="{405+(W-p['usb']['cutout_width'])*k/2}" y="{416+(H-p['usb']['cutout_bottom']-p['usb']['cutout_height'])*k}" width="{p['usb']['cutout_width']*k}" height="{p['usb']['cutout_height']*k}" rx="3" fill="#91a99b" stroke="#536c5b"/>
<text x="635" y="452" class="label">{p['usb']['cutout_width']:g} × {p['usb']['cutout_height']:g} mm</text><text x="635" y="479" class="small">用实际插头核对可插到底</text>
<text x="50" y="574" font-size="17" font-weight="600">打印 base.stl + lid.stl；PH2.0与主板插头均在壳外</text>
<text x="50" y="607" class="small">模块参考16.2 × 12 × 4.4 mm；BAT两线接电池，5V两线接主板；焊点见接线关系图。</text>
<text x="50" y="634" class="small">图中模块与走线是包络示意，不能代替焊点三维测量、打印试装和实际拉力检查。</text></svg>''')
    (HERE/'output/drawing.svg').write_text(''.join(pieces),encoding='utf-8')

if __name__=='__main__':run()
