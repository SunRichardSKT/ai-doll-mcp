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
    page=TEMPLATE
    replacements={
        'AI Doll · 外壳 P01':'AI Doll · 已制板电池卡扣壳 P03',
        'AI DOLL / HARDWARE / V22-ENC-P01':'AI DOLL / ORDERED PCB 20260920 / CASE P03',
        '圆角双片外壳':'电池仓 · 卡扣双片外壳',
        '46.29 × 56.45':'62.00 × 100.45',
        '20.4 / 1.8 mm':f"{data['dimensions']['height']:.1f} / 1.8 mm",
        '4 × M2':'4 处可释放卡扣',
        '为当前布线板留出的空间':'已制板 + 103450 电池',
        'J9 日常供电 · USB 开盖维护 · 八路带线传感输入':'免螺丝上盖 · 独立锂电池仓 · LED 观察窗',
        '边缘托座固定 PCB，不使用板上的线束固定孔。':'边缘托座固定旧版主板，无需打孔；保留八路带线传感接口与壳体扎带通道。',
        '正面独立 J9 出线口与开关检修口；松开上盖后操作 USB、BOOT / RST。天线端不布置紧固螺钉。':'底盒侧窗可按压释放卡扣：先解除一对、轻抬盖，再解除另一对。右侧 J9 出线，USB、BOOT / RST 开盖维护；14 × 12 mm 窗观察模块灯。',
        '元件高度、板厚与线径为预留假设。灰色元件是包络参考，USB 不是已验证插拔模型。':'前方独立 52 × 36 × 12 mm 电池净空，黄色块为 50 × 34 × 10 mm 103450 参考。出线端另留 7.2 mm，导线松弯向上，经隔板顶槽进入 PH2.0 区；不挤电芯或封边。',
        '先打印 fit_tray，再检查焊点、线束弯折和开关可达性。此结构没有防水等级，也不包含电池。':'建议 PETG 打印；卡扣弹性和电池封边需实装。单节 3.7 V 电池不能直接代替 J9 的 5 V，充电/保护/升压需另选。观察窗无防水等级。',
        '模型来自当前 PCB 实际 XY 回读；Z 向包络采用公开标注的假设。':'仅打印底盒与上盖两件。按旧版实板及约 8 mm 模块叠高设计，实物卡扣、LED、插头尺寸仍待核对。',
        '2026-10-17':'2026-10-20',
        '<i style="background:#22736c"></i>PCB 位置参考</span>':'<i style="background:#22736c"></i>PCB 位置参考</span><span><i style="background:#dfbc5e"></i>103450 电池参考</span>'
    }
    for before,after in replacements.items():
        assert before in page,before
        page=page.replace(before,after)
    (OUT/'preview.html').write_text(page.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf-8')
    print('Self-contained preview:',OUT/'preview.html')

if __name__=='__main__':run()
