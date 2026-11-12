"""Produce a self-contained orbit viewer and a dimension reference from CAD meshes."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'

TEMPLATE=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Doll · 外壳 P01</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f2f3ed;color:#24372f;font-family:Segoe UI,Microsoft YaHei,sans-serif}header{padding:30px 38px 20px;display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid #d5dbcf}h1{margin:4px 0;font-size:32px;font-weight:650;letter-spacing:-1px}.eyebrow{font-size:12px;letter-spacing:2px;color:#627164}.badge{background:#e5ddc5;padding:10px 15px;border-radius:20px;font-size:13px;color:#6d5733}main{display:grid;grid-template-columns:minmax(600px,1fr) 330px;gap:24px;padding:24px 32px}.view{background:#e5e9df;border-radius:24px;overflow:hidden;position:relative;box-shadow:0 16px 45px #3448390a}canvas{width:100%;height:660px;display:block;cursor:grab;touch-action:none}.toolbar{padding:16px;display:flex;gap:7px;flex-wrap:wrap}button{background:#f9faf6;border:1px solid #cbd3c3;border-radius:10px;padding:10px 15px;color:#334a3b;cursor:pointer;font:inherit;font-size:13px}button.active{background:#304e3d;color:white;border-color:#304e3d}.hint{position:absolute;left:24px;bottom:20px;font-size:12px;color:#657463}.pill{position:absolute;right:22px;bottom:18px;background:#f6f7f1;padding:8px 13px;border-radius:14px;font-size:12px}.card{background:#fafbf7;border:1px solid #d9dfd2;border-radius:18px;padding:22px;margin-bottom:16px}h2{font-size:19px;margin:0 0 14px}.spec{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid #e4e8dc;font-size:13px}.spec:last-child{border:0}.spec strong{font-size:16px;font-weight:600}p{font-size:13px;line-height:1.85;margin:8px 0;color:#526451}.note{background:#ece5d2;border-color:#e0d4b6}.legend{display:flex;gap:20px;flex-wrap:wrap;padding:0 30px 22px;font-size:12px;color:#586c58}i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}.footer{padding:0 38px 26px;font-size:12px;color:#6d7a67}a{color:#41634e} @media(max-width:950px){main{grid-template-columns:1fr}canvas{height:540px}header{align-items:start;gap:20px}.badge{max-width:190px}.card{display:inline-block;vertical-align:top;width:100%}}
</style>
<header><div><div class="eyebrow">AI DOLL / HARDWARE / V22-ENC-P01</div><h1>圆角双片外壳</h1><p>J9 日常供电 · USB 开盖维护 · 八路带线传感输入</p></div><span class="badge">首版试装样件 · 尚未实物验证</span></header>
<main><section class="view"><div class="toolbar"><button data-mode="exploded" class="active">打开上盖</button><button data-mode="assembled">装配</button><button data-mode="base">仅底盒</button><button data-mode="lid">仅上盖</button><button id="cut">查看内部剖切</button><button id="reset">复位视角</button></div><canvas id="c"></canvas><div class="legend"><span><i style="background:#bdc8bb"></i>底盒 / 托座</span><span><i style="background:#e5eadf"></i>可拆卸上盖</span><span><i style="background:#22736c"></i>PCB 位置参考</span></div><div class="hint">拖动旋转 · 滚轮缩放 · 文件可离线打开</div><div class="pill" id="modeName">打开上盖</div></section>
<aside><div class="card"><h2>为当前布线板留出的空间</h2><div class="spec"><span>外壳外形</span><strong>46.29 × 56.45</strong></div><div class="spec"><span>总高 / 壁厚</span><strong>20.4 / 1.8 mm</strong></div><div class="spec"><span>主板尺寸</span><strong>34.29 × 44.45</strong></div><div class="spec"><span>上盖紧固</span><strong>4 × M2</strong></div><div class="spec"><span>侧面线孔</span><strong>8 × 4.4 mm</strong></div></div>
<div class="card"><h2>可拆、可维护</h2><p>边缘托座固定 PCB，不使用板上的线束固定孔。线束从敞口槽放入，盖上的挡片补齐槽口，无需让 SM 塑壳穿过小孔。</p><p>正面独立 J9 出线口与开关检修口；松开上盖后操作 USB、BOOT / RST。天线端不布置紧固螺钉。</p></div>
<div class="card note"><h2>先试装，再定版</h2><p>元件高度、板厚与线径为预留假设。灰色元件是包络参考，USB 不是已验证插拔模型。</p><p>先打印 fit_tray，再检查焊点、线束弯折和开关可达性。此结构没有防水等级，也不包含电池。</p></div>
<p><a href="base.stl">底盒 STL</a> · <a href="lid.stl">上盖 STL</a> · <a href="assembly_reference.step">STEP 装配参考</a></p></aside></main>
<div class="footer">模型来自当前 PCB 实际 XY 回读；Z 向包络采用公开标注的假设。剖切仅用于观察，不改变打印模型。单位 mm。2026-10-17</div>
<script>
const data=__DATA__,c=document.getElementById('c'),gl=c.getContext('webgl',{antialias:true,preserveDrawingBuffer:true});let mode='exploded',cut=false,yaw=-.48,elev=.91,zoom=1,drag=null;
if(!gl)throw Error('此浏览器未启用 WebGL，请查看 PNG 或使用 STEP 查看器');
function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 position;attribute vec3 color;varying vec3 vColor;void main(){gl_Position=vec4(position,1.0);vColor=color;}'));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 vColor;void main(){gl_FragColor=vec4(vColor,1.0);}'));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);for(const [name,offset] of [['position',0],['color',12]]){const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,3,gl.FLOAT,false,24,offset)}gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
const dims=data.dimensions, hex=s=>[1,3,5].map(i=>parseInt(s.slice(i,i+2),16));
const meshes=data.parts.map(p=>({...p,rgb:hex(p.color)}));
function draw(){const r=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio,2);c.width=r.width*dpr;c.height=r.height*dpr;const w=r.width,h=r.height;gl.viewport(0,0,c.width,c.height);gl.clearColor(229/255,233/255,223/255,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
 const explode=mode==='exploded',cy=Math.cos(yaw),sy=Math.sin(yaw),se=Math.sin(elev),ce=Math.cos(elev);
 const basis=([x,y,z])=>{const xx=cy*x-sy*y,yy=sy*x+cy*y;return[xx,se*yy+ce*z,-ce*yy+se*z]};
 const shown=meshes.filter(p=>mode==='lid'?p.name==='lid':mode==='base'?p.name!=='lid':true);
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
 for(const part of shown){const off=part.name==='lid'&&explode?[dims.width+13,0,-11]:[0,0,0];for(const v of part.geometry.vertices){const q=basis(v.map((x,i)=>x+off[i]));xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1]);}}
 const scale=Math.min((w-72)/Math.max(1,xmax-xmin),(h-80)/Math.max(1,ymax-ymin))*zoom,centerX=(xmin+xmax)/2,centerY=(ymin+ymax)/2;
 const project=v=>{const q=basis(v);return[w/2+scale*(q[0]-centerX),h/2-scale*(q[1]-centerY),q[2]]};
 const floats=[];
 for(const part of meshes){if(mode==='lid'&&part.name!=='lid')continue;if(mode==='base'&&part.name==='lid')continue;
  const off=part.name==='lid'&&explode?[dims.width+13,0,-11]:[0,0,0];const verts=part.geometry.vertices.map(v=>[v[0]+off[0],v[1]+off[1],v[2]+off[2]]),q=verts.map(project);
  for(const f of part.geometry.faces){const a=verts[f[0]],b=verts[f[1]],cc=verts[f[2]];if(cut&&part.name==='base'&&(a[1]+b[1]+cc[1])/3<dims.length*.45&&(a[2]+b[2]+cc[2])/3>2)continue;
   const u=b.map((v,i)=>v-a[i]),v=cc.map((v,i)=>v-a[i]),n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],nl=Math.hypot(...n)||1;
   const light=.68+.32*Math.max(0,(n[0]*-.3+n[1]*-.4+n[2]*.85)/nl),color=part.rgb.map(v=>Math.min(255,Math.round(v*light)));
   for(const i of f){const v=q[i];floats.push(v[0]*2/w-1,1-v[1]*2/h,-v[2]/250,...color.map(x=>x/255));}
  }
 }
 gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(floats),gl.DYNAMIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,floats.length/6);if(gl.getError()!==gl.NO_ERROR)throw Error('WebGL render failed');
 document.getElementById('modeName').textContent=({exploded:'打开上盖',assembled:'装配',base:'仅底盒',lid:'仅上盖'})[mode]+(cut?' · 观察剖切':'');
}
document.querySelectorAll('[data-mode]').forEach(el=>el.onclick=()=>{mode=el.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('active',x===el));draw()});
document.getElementById('cut').onclick=e=>{cut=!cut;e.target.classList.toggle('active',cut);draw()};document.getElementById('reset').onclick=()=>{yaw=-.48;elev=.91;zoom=1;draw()};
c.onpointerdown=e=>{drag=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId)};c.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;elev=Math.max(.12,Math.min(1.5,elev+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];draw()};c.onpointerup=()=>drag=null;c.onwheel=e=>{e.preventDefault();zoom=Math.max(.5,Math.min(2,zoom*Math.exp(-e.deltaY*.001)));draw()};window.addEventListener('resize',draw);draw();window.modelReady=true;
</script></html>'''


def run():
    data=json.loads((OUT/'meshes.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    page=TEMPLATE
    replacements={
        'AI Doll · 外壳 P01':'AI Doll · 第一代最终版核心电池壳',
        'AI DOLL / HARDWARE / V22-ENC-P01':'AI DOLL / GEN 1 / FINAL',
        '圆角双片外壳':'第一代最终版 · 卡扣电池壳',
        '首版试装样件 · 尚未实物验证':'新版PCB专用 · 三件打印',
        'J9 日常供电 · USB 开盖维护 · 八路带线传感输入':'下层电池 · 中间绝缘托板 · 上层主板 · 下沉开关口',
        '46.29 × 56.45':'46.29 × 56.45 mm',
        '20.4 / 1.8 mm':f"{data['dimensions']['height']:.1f} / 1.8 mm",
        '4 × M2':'前后四点卡扣',
        '为当前布线板留出的空间':'缩小长宽，电池下置',
        '边缘托座固定 PCB，不使用板上的线束固定孔。线束从敞口槽放入，盖上的挡片补齐槽口，无需让 SM 塑壳穿过小孔。':'电池平放在底层，长边沿外壳长度方向。1.8 mm可拆绝缘托板同时承托主板，将载荷传到壳壁侧轨。托板上方给2.8 mm底面元件及修剪后的焊脚再留1 mm间隙。',
        '正面独立 J9 出线口与开关检修口；松开上盖后操作 USB、BOOT / RST。天线端不布置紧固螺钉。':'需要打印底壳、绝缘托板、上盖三件。托板隔离底面元件和电芯，并可单独取出更换电池。前后墙卡扣避开八路侧面线槽。USB从正面直插；BOOT、RST开盖维护。',
        '元件高度、板厚与线径为预留假设。灰色元件是包络参考，USB 不是已验证插拔模型。':f"开关移到右后方，顶部与右侧可拨动；正面USB口15 × 9 mm，按14 × 8 mm直头胶壳校核插入通道。导向单边间隙{p['lid_guide_clearance']:.2f} mm，挂钩咬合{p['wall']-p['snap_tip_inset']:.2f} mm。",
        '先打印 fit_tray，再检查焊点、线束弯折和开关可达性。此结构没有防水等级，也不包含电池。':'电池净空36 × 52 × 12 mm，出线向上经过托板开口；短边水平余量约1.85 mm，原厂线弯曲及封边必须试装。建议PETG，不压电芯。103450为3.7V 2000mAh，PH2.0接头留在壳外，接独立充电模块；J9接模块5V输出。',
        '模型来自当前 PCB 实际 XY 回读；Z 向包络采用公开标注的假设。剖切仅用于观察，不改变打印模型。单位 mm。2026-10-17':'对应用户最终丝印版PCB；核心与充电模块各用独立外壳。底壳、绝缘载架、上盖需配套打印；不与旧板外壳混用。黄色电池及绿色PCB不要打印。单位 mm。2026-11-09',
        '<button id="cut">':'<button data-mode="tray">绝缘托板</button><button id="side">层叠侧视</button><button id="cut">',
        '<i style="background:#22736c"></i>PCB 位置参考</span>':'<i style="background:#22736c"></i>PCB 位置参考</span><span><i style="background:#dfbc5e"></i>103450电池</span><span><i style="background:#c7af8a"></i>可拆绝缘托板</span>',
        '<a href="lid.stl">上盖 STL</a>':'<a href="tray.stl">绝缘托板 STL</a> · <a href="lid.stl">上盖 STL</a>',
        "mode==='lid'?p.name==='lid':mode==='base'?p.name!=='lid':true":"mode==='lid'?p.name==='lid':mode==='tray'?p.name==='tray':mode==='base'?p.name!=='lid':true",
        "const off=part.name==='lid'&&explode?[dims.width+13,0,-11]:[0,0,0]":"const off=explode?[0,0,part.name==='lid'?44:part.name==='tray'?12:part.name==='base'||part.name==='Battery_103450_reference'?0:24]:[0,0,0]",
        "if(mode==='lid'&&part.name!=='lid')continue;":"if(mode==='lid'&&part.name!=='lid')continue;if(mode==='tray'&&part.name!=='tray')continue;",
        "base:'仅底盒',lid:'仅上盖'":"base:'底盒与内部',lid:'仅上盖',tray:'绝缘托板'",
        "document.getElementById('cut').onclick":"document.getElementById('side').onclick=()=>{yaw=0;elev=.12;zoom=1;draw()};document.getElementById('cut').onclick",
    }
    for before,after in replacements.items():
        assert before in page,before
        page=page.replace(before,after)
    stack=audit['heightStackMm']
    rows=[('电池顶',stack['batteryReferenceTop']),('托板顶',stack['trayTop']),
          ('底面元件最低处',stack['bottomComponentBottom']),('主板底',stack['pcbBottom']),('开关顶',stack['switchActuatorTip'])]
    extra='<div class="card"><h2>从底面向上的层叠高度</h2>'+''.join(
        f'<div class="spec"><span>{name}</span><strong>{value:.1f} mm</strong></div>' for name,value in rows)+\
        '</div><p><a href="../README.md">试装与打印说明</a> · <a href="stack.svg">带尺寸侧剖示意</a></p>'
    extra+='<div class="card"><h2>结构加固版 · 2026-11-13</h2><p>取消细长托板压杆，改用主板边缘宽肋；托板承托加宽至4 mm，限位挡块加厚至1.6 mm。侧面上部细隔片合并为连续窗口和宽盖边。</p><p>卡扣宽根连接，活动段厚1.25 mm；导向边厚1.4 mm。底壳、托板、上盖须整套重打，不与旧件混用。</p><p>PETG、0.16～0.20 mm层高、4道壁。按STL现有方向切片；实际扣合与耐久需首件试装。</p></div>'
    page=page.replace('</aside>',extra+'</aside>')
    page=page.replace('V2.2','C3插座版').replace('P02','第一代最终版').replace('46.29 × 56.45','42.89 × 56.45').replace('侧面线孔','侧插窗口').replace('8 × 4.4 mm','8 × 7 mm + 1 × 9 mm').replace('侧面线槽','侧面插座').replace('八路带线传感输入','八路锁扣板载插座')
    page=page.replace('下沉开关口','右后方开关 · 左侧BAT出线／5V锁扣座').replace('缩小长宽，电池下置','板载插座，电池下置')
    page=page.replace('第一代最终版 · 卡扣电池壳','第一代最终版 · 加固电池壳').replace('8 × 7 mm + 1 × 9 mm','左右连通窗口').replace('2026-11-09','2026-11-13')
    (OUT/'preview.html').write_text(page.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf-8')
    side_diagram(audit,p)
    from render_wiring import run as draw_wiring
    draw_wiring()
    print('Self-contained preview:',OUT/'preview.html')


def side_diagram(audit,p):
    """Annotated nominal longitudinal section, separate from the true CAD view."""
    stack=audit['heightStackMm'];scale=10;left=75;bottom=490
    def rect(y,z,length,height,color,stroke='#405a4d',dash=''):
        return f'<rect x="{left+y*scale}" y="{bottom-(z+height)*scale}" width="{length*scale}" height="{height*scale}" fill="{color}" stroke="{stroke}" stroke-width="1.5" {dash}/>'
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="650" viewBox="0 0 1040 650">',
         '<rect width="1040" height="650" fill="#f2f3ed"/>',
         '<g font-family="Microsoft YaHei,Segoe UI,sans-serif" fill="#24372f">',
         '<text x="54" y="48" font-size="27" font-weight="bold">第一代最终版 · 103450堆叠外壳</text>',
         '<text x="54" y="79" font-size="16">42.89 × 56.45 × 33.5 mm · 下图为名义层高与侧投影，非加工图</text>',
         rect(0,0,p['outer_length'],audit['dimensionsMm']['height'],'#dce4d5'),
         rect(p['wall'],p['floor'],p['outer_length']-2*p['wall'],stack['roofBottom']-p['floor'],'#f9faf6')]
    b=p['battery'];svg.append(rect(b['y'],b['z'],b['length'],b['height'],'#dfbc5e'))
    svg.append(rect(2.15,stack['trayBottom'],p['outer_length']-4.3,p['tray_thickness'],'#c7af8a'))
    svg.append(rect(6,stack['pcbBottom'],44.45,1.6,'#388679'))
    svg.append(rect(33.18,stack['bottomComponentBottom'],7.62,2.8,'#73796f'))
    svg.append(rect(26.63,stack['pcbTop'],22.5,6,'#273e4d'))
    reference=json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'))
    sw=next(c for c in reference['components'] if c['ref']=='SW1')['bbox']
    svg.append(rect(p['board_offset'][1]+sw['minY'],stack['pcbTop'],sw['maxY']-sw['minY'],p['switch_body_height'],'#887b63'))
    svg.extend([
        '<text x="308" y="430" font-size="20">103450 电池</text>',
        '<text x="352" y="256" font-size="17" fill="#fff">SuperMini</text>',
        '<text x="490" y="243" font-size="13">右后开关（侧投影）</text>'])
    rows=[('主盖外顶',audit['dimensionsMm']['height']),('盖内顶',stack['roofBottom']),('模块参考顶',stack['moduleTop']),
          ('开关拨杆顶',stack['switchActuatorTip']),('PCB顶面',stack['pcbTop']),('PCB底面',stack['pcbBottom']),
          ('底面元件最低处',stack['bottomComponentBottom']),('绝缘载架顶',stack['trayTop']),
          ('电池参考顶',stack['batteryReferenceTop'])]
    for i,(label,value) in enumerate(rows):
        yy=bottom-value*scale
        svg.append(f'<path d="M 650 {yy} H 685" stroke="#9baa98"/>')
        svg.append(f'<text x="710" y="{147+i*35}" font-size="16">{label}　{value:.1f} mm</text>')
    svg.extend(['<text x="54" y="551" font-size="16">打印三件：底壳 + 可拆绝缘载架 + 卡扣上盖；USB从正面直插；BOOT、RST开盖维护。</text>',
                '<text x="54" y="581" font-size="15">103450 · 3.7V 2000mAh · PH2.0接独立充电板；电池净空36×52×12 mm。</text>',
                '<text x="54" y="611" font-size="14">PCB板厚、贴片模块高度、焊脚和电池封边须用实物试装核对。</text></g></svg>'])
    (OUT/'stack.svg').write_text(''.join(svg),encoding='utf-8')


if __name__=='__main__':
    run()

