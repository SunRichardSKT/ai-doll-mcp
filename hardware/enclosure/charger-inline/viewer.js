
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
 const shown=meshes.filter(p=>mode==='lid'?p.name==='lid':mode==='base'?p.name==='base':mode==='inside'?p.name!=='lid':true);
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
 for(const part of shown){const off=part.name==='lid'&&explode?[dims.width+12,0,0]:[0,0,0];for(const v of part.geometry.vertices){const q=basis(v.map((x,i)=>(part.name==='lid'&&explode&&i===2?dims.height-x:x)+off[i]));xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1]);}}
 const scale=Math.min((w-72)/Math.max(1,xmax-xmin),(h-80)/Math.max(1,ymax-ymin))*zoom,centerX=(xmin+xmax)/2,centerY=(ymin+ymax)/2;
 const project=v=>{const q=basis(v);return[w/2+scale*(q[0]-centerX),h/2-scale*(q[1]-centerY),q[2]]};
 const floats=[];
 for(const part of meshes){if(mode==='lid'&&part.name!=='lid')continue;if(mode==='base'&&part.name!=='base')continue;if(mode==='inside'&&part.name==='lid')continue;
  const off=part.name==='lid'&&explode?[dims.width+12,0,0]:[0,0,0];const verts=part.geometry.vertices.map(v=>[v[0]+off[0],v[1]+off[1],(part.name==='lid'&&explode?dims.height-v[2]:v[2])+off[2]]),q=verts.map(project);
  for(const f of part.geometry.faces){const a=verts[f[0]],b=verts[f[1]],cc=verts[f[2]];if(cut&&part.name==='base'&&(a[1]+b[1]+cc[1])/3<dims.length*.45&&(a[2]+b[2]+cc[2])/3>2)continue;
   const u=b.map((v,i)=>v-a[i]),v=cc.map((v,i)=>v-a[i]),n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],nl=Math.hypot(...n)||1;
   const light=.68+.32*Math.max(0,(n[0]*-.3+n[1]*-.4+n[2]*.85)/nl),color=part.rgb.map(v=>Math.min(255,Math.round(v*light)));
   for(const i of f){const v=q[i];floats.push(v[0]*2/w-1,1-v[1]*2/h,-v[2]/250,...color.map(x=>x/255));}
  }
 }
 gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(floats),gl.DYNAMIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,floats.length/6);if(gl.getError()!==gl.NO_ERROR)throw Error('WebGL render failed');
 document.getElementById('modeName').textContent=({exploded:'打开上盖 · 内侧朝上',assembled:'装配',base:'仅底壳',inside:'内部装配',lid:'仅上盖'})[mode]+(cut?' · 观察剖切':'');
}
document.querySelectorAll('[data-mode]').forEach(el=>el.onclick=()=>{mode=el.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>x.classList.toggle('active',x===el));draw()});
document.getElementById('cut').onclick=e=>{cut=!cut;e.target.classList.toggle('active',cut);draw()};document.getElementById('reset').onclick=()=>{yaw=-.48;elev=.91;zoom=1;draw()};
c.onpointerdown=e=>{drag=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId)};c.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;elev=Math.max(.12,Math.min(1.5,elev+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];draw()};c.onpointerup=()=>drag=null;c.onwheel=e=>{e.preventDefault();zoom=Math.max(.5,Math.min(2,zoom*Math.exp(-e.deltaY*.001)));draw()};window.addEventListener('resize',draw);draw();window.modelReady=true;
