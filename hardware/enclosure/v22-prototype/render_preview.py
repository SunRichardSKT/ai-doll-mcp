"""Produce a self-contained orbit viewer and a dimension reference from CAD meshes."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'

TEMPLATE=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Doll · V22 卡扣电池外壳 P02</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f2f3ed;color:#24372f;font-family:Segoe UI,Microsoft YaHei,sans-serif}header{padding:30px 38px 20px;display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid #d5dbcf}h1{margin:4px 0;font-size:32px;font-weight:650;letter-spacing:-1px}.eyebrow{font-size:12px;letter-spacing:2px;color:#627164}.badge{background:#e5ddc5;padding:10px 15px;border-radius:20px;font-size:13px;color:#6d5733}main{display:grid;grid-template-columns:minmax(600px,1fr) 330px;gap:24px;padding:24px 32px}.view{background:#e5e9df;border-radius:24px;overflow:hidden;position:relative;box-shadow:0 16px 45px #3448390a}canvas{width:100%;height:660px;display:block;cursor:grab;touch-action:none}.toolbar{padding:16px;display:flex;gap:7px;flex-wrap:wrap}button{background:#f9faf6;border:1px solid #cbd3c3;border-radius:10px;padding:10px 15px;color:#334a3b;cursor:pointer;font:inherit;font-size:13px}button.active{background:#304e3d;color:white;border-color:#304e3d}.hint{position:absolute;left:24px;bottom:20px;font-size:12px;color:#657463}.pill{position:absolute;right:22px;bottom:18px;background:#f6f7f1;padding:8px 13px;border-radius:14px;font-size:12px}.card{background:#fafbf7;border:1px solid #d9dfd2;border-radius:18px;padding:22px;margin-bottom:16px}h2{font-size:19px;margin:0 0 14px}.spec{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid #e4e8dc;font-size:13px}.spec:last-child{border:0}.spec strong{font-size:16px;font-weight:600}p{font-size:13px;line-height:1.85;margin:8px 0;color:#526451}.note{background:#ece5d2;border-color:#e0d4b6}.legend{display:flex;gap:20px;flex-wrap:wrap;padding:0 30px 22px;font-size:12px;color:#586c58}i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}.footer{padding:0 38px 26px;font-size:12px;color:#6d7a67}a{color:#41634e} @media(max-width:950px){main{grid-template-columns:1fr}canvas{height:540px}header{align-items:start;gap:20px}.badge{max-width:190px}.card{display:inline-block;vertical-align:top;width:100%}}
</style>
<header><div><div class="eyebrow">AI DOLL / HARDWARE / V22-ENC-P02</div><h1>卡扣电池外壳</h1><p>四处可释放卡扣 · 独立 103450 电池仓 · 指示灯观察窗</p></div><span class="badge">V22 新板样件 · 尚未实物试装</span></header>
<main><section class="view"><div class="toolbar"><button data-mode="exploded" class="active">打开上盖</button><button data-mode="assembled">装配</button><button data-mode="base">仅底盒</button><button data-mode="lid">仅上盖</button><button id="cut">查看内部剖切</button><button id="reset">复位视角</button></div><canvas id="c"></canvas><div class="legend"><span><i style="background:#bdc8bb"></i>底盒 / 隔板</span><span><i style="background:#e5eadf"></i>卡扣上盖</span><span><i style="background:#22736c"></i>PCB 参考</span><span><i style="background:#e9ba45"></i>103450 电池参考</span></div><div class="hint">拖动旋转 · 滚轮缩放 · 文件可离线打开</div><div class="pill" id="modeName">打开上盖</div></section>
<aside><div class="card"><h2>两件打印，无需螺丝</h2><div class="spec"><span>外壳外形</span><strong>62 × 100.45 mm</strong></div><div class="spec"><span>总高 / 壁厚</span><strong>20.4 / 1.8 mm</strong></div><div class="spec"><span>电池仓净空</span><strong>52 × 36 × 12 mm</strong></div><div class="spec"><span>电池出线端净宽</span><strong>7.2 mm</strong></div><div class="spec"><span>上盖紧固</span><strong>4 处释放卡扣</strong></div><div class="spec"><span>观察窗口</span><strong>14 × 12 mm</strong></div></div>
<div class="card"><h2>分开的电池与主板空间</h2><p>103450 电池平放在前仓，独立绝缘隔板与主板分隔。原厂引线端朝 +X（右侧），端部留 7.2 mm 净宽，导线松弯到电池上方，再经顶开隔板槽进入 12 × 8 × 10 mm 插头区。避免夹线、挤压电芯或强折封边。</p><p>右侧独立 J9 电源出线槽避开电池。侧壁窗口可向内按压卡脚释放上盖；USB、BOOT / RST 仍开盖维护。指示灯窗口位置可调，需按实际模块核对。</p></div>
<div class="card note"><h2>打印前先核对</h2><p>黄色电池和灰色元件是非打印参考。电池以 50 × 34 × 10 mm 标称尺寸建模；封边、保护板与 PH2.0 实物尺寸需另量。</p><p>建议 PETG，先空盒试扣，再断电装板。电池仅预留机械空间；单节 3.7 V 不能直接接 J9 的 5 V 输入，充电、保护和升压需匹配电源管理。</p></div>
<p><a href="base.stl">底盒 STL</a> · <a href="lid.stl">上盖 STL</a> · <a href="assembly_reference.step">STEP 装配参考</a></p></aside></main>
<div class="footer">V22 新板 / 模块高 6 mm。模型来自 PCB 实际 XY 回读；Z 向包络及 LED 位置为标注假设。卡扣弹性、接头装配及实物温升待验证。单位 mm。2026-10-20</div>
<script>
const data=__DATA__,c=document.getElementById('c'),gl=c.getContext('webgl',{antialias:true,preserveDrawingBuffer:true});let mode='exploded',cut=false,yaw=-.48,elev=.91,zoom=1,drag=null;
if(!gl)throw Error('此浏览器未启用 WebGL，请查看 PNG 或使用 STEP 查看器');
function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec3 position;attribute vec3 color;varying vec3 vColor;void main(){gl_Position=vec4(position,1.0);vColor=color;}'));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec3 vColor;void main(){gl_FragColor=vec4(vColor,1.0);}'));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);for(const [name,offset] of [['position',0],['color',12]]){const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,3,gl.FLOAT,false,24,offset)}gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
const dims=data.dimensions, hex=s=>[1,3,5].map(i=>parseInt(s.slice(i,i+2),16));
const meshes=data.parts.map(p=>({...p,rgb:hex(p.color)}));
function draw(){const r=c.getBoundingClientRect(),dpr=Math.min(devicePixelRatio,2);c.width=r.width*dpr;c.height=r.height*dpr;const w=r.width,h=r.height;gl.viewport(0,0,c.width,c.height);gl.clearColor(229/255,233/255,223/255,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
 const explode=mode==='exploded',centerX=explode?dims.width+15:dims.width/2,centerY=dims.length/2,centerZ=9;
 const scale=Math.min(w/(explode?dims.width*2+35:dims.width+40),h/(dims.length+30))*zoom,cy=Math.cos(yaw),sy=Math.sin(yaw),se=Math.sin(elev),ce=Math.cos(elev);
 const project=([x,y,z])=>{x-=centerX;y-=centerY;z-=centerZ;const xx=cy*x-sy*y,yy=sy*x+cy*y;return[w/2+scale*xx,h/2-scale*(se*yy+ce*z),-ce*yy+se*z]};
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
    (OUT/'preview.html').write_text(TEMPLATE.replace('__DATA__',json.dumps(data,separators=(',',':'))),encoding='utf-8')
    print('Self-contained preview:',OUT/'preview.html')

if __name__=='__main__':run()
