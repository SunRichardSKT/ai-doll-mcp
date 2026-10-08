// Shared by the ESP32 portal and the computer page; labels are always rendered as text.
let channelDraft=[],channelCapabilities={};
const channelTypeLabels={pressure:'压力输入',temperature:'温度输入',vibration:'震动输出'};
const channelDriverLabels={simulation:'仅模拟',mux_adc:'4051 模拟输入',gpio_adc:'独立 ADC',gpio_pwm:'独立 GPIO PWM'};
function readChannelDraft(){
 return channelDraft.map(c=>{
  const type=$('type'+c.channel).value,driver=$('driver'+c.channel).value;
  const result={channel:c.channel,name:$('part'+c.channel).value,type,driver,enabled:$('channelEnabled'+c.channel).checked,
   options:JSON.parse($('options'+c.channel).value||'{}')};
  if(driver==='mux_adc')result.mux_port=Number($('binding'+c.channel).value);
  if(driver==='gpio_adc'||driver==='gpio_pwm')result.gpio=Number($('binding'+c.channel).value);
  return result;
 });
}
function fillChannelSelects(){
 for(const id of ['channel','vibrationChannel']){
  const select=$(id);if(!select)continue;const previous=select.value;select.replaceChildren();
  for(const c of channelDraft.filter(c=>c.enabled&&(id==='vibrationChannel'?c.type==='vibration':c.type!=='vibration')))
   select.add(new Option('CH'+c.channel+' · '+c.name+' · '+(channelTypeLabels[c.type]||c.type),c.channel));
  if(Array.from(select.options).some(o=>o.value===previous))select.value=previous;
 }
 for(const id of ['vibrate','stopVibration'])if($(id))$(id).disabled=!$('vibrationChannel').options.length;
 inputTypeChanged();
}
function inputTypeChanged(){
 const c=channelDraft.find(c=>c.channel===Number($('channel').value));
 const temp=c&&c.type==='temperature',input=$('pressure');
 input.min=temp?-40:0;input.max=temp?125:4095;input.step=temp?.1:1;
 input.value=temp?32:3200;if($('inputUnit'))$('inputUnit').textContent=temp?'模拟温度（℃）':'压力原始值（0 表示释放）';
 if($('release'))$('release').disabled=!c||temp;
}
function renderChannelEditor(){
 $('parts').replaceChildren();
 for(const c of channelDraft){
  const box=document.createElement('div');box.className='channel-card';
  const title=document.createElement('strong');title.textContent='CH'+c.channel;box.append(title);
  const name=document.createElement('input');name.id='part'+c.channel;name.name='channel_name';name.value=c.name;name.maxLength=96;name.setAttribute('aria-label','CH'+c.channel+' 部位或用途');box.append(name);
  const type=document.createElement('select');type.id='type'+c.channel;type.setAttribute('aria-label','CH'+c.channel+' 类型');
  for(const t of channelCapabilities.types)type.add(new Option(channelTypeLabels[t.type]||t.type,t.type));type.value=c.type;box.append(type);
  const driver=document.createElement('select');driver.id='driver'+c.channel;driver.setAttribute('aria-label','CH'+c.channel+' 接口');
  for(const d of channelCapabilities.types.find(t=>t.type===c.type).drivers)driver.add(new Option(channelDriverLabels[d]||d,d));driver.value=c.driver;box.append(driver);
  const bindingLabel=document.createElement('label'),binding=document.createElement('input');binding.id='binding'+c.channel;binding.type='number';binding.step=1;binding.value=c.mux_port??c.gpio??0;
  const caption=document.createElement('span');bindingLabel.append(caption,binding);box.append(bindingLabel);
  const updateBinding=()=>{caption.textContent=driver.value==='mux_adc'?'4051 端口（0～7）':'GPIO 编号';bindingLabel.hidden=driver.value==='simulation';};updateBinding();
  const enabledLabel=document.createElement('label'),enabled=document.createElement('input');enabled.type='checkbox';enabled.id='channelEnabled'+c.channel;enabled.checked=c.enabled;enabledLabel.append(enabled,document.createTextNode(' 启用此通道'));box.append(enabledLabel);
  const advanced=document.createElement('details'),summary=document.createElement('summary'),options=document.createElement('textarea');summary.textContent='阈值 / 温度参数';options.id='options'+c.channel;options.value=JSON.stringify(c.options||{},null,2);options.rows=5;advanced.append(summary,options);box.append(advanced);
  const remove=document.createElement('button');remove.type='button';remove.textContent='移除此通道';remove.disabled=channelDraft.length<=1;
  remove.onclick=()=>{try{channelDraft=readChannelDraft().filter(x=>x.channel!==c.channel);renderChannelEditor()}catch(e){$('error').textContent=e.message}};box.append(remove);
  driver.onchange=()=>{if(driver.value==='gpio_adc')binding.value=1;if(driver.value==='gpio_pwm')binding.value=10;updateBinding()};
  type.onchange=()=>{try{channelDraft=readChannelDraft();const next=channelDraft.find(x=>x.channel===c.channel);next.driver='simulation';next.options={};delete next.mux_port;delete next.gpio;renderChannelEditor()}catch(e){$('error').textContent=e.message}};
  $('parts').append(box);
 }
 fillChannelSelects();
 if($('calibrationChannel'))fillCalibrationChannels();
}
async function loadChannels(){
 channelCapabilities=await tool('get_channel_capabilities');channelDraft=(await tool('get_channel_config')).channels;renderChannelEditor();
 $('addChannel').onclick=()=>{try{channelDraft=readChannelDraft();const id=Array.from({length:channelCapabilities.max_channels},(_,i)=>i).find(i=>!channelDraft.some(c=>c.channel===i));if(id===undefined)throw Error('已达到逻辑通道上限');channelDraft.push({channel:id,name:'CH'+id,type:'pressure',driver:'simulation',enabled:true,options:{}});channelDraft.sort((a,b)=>a.channel-b.channel);renderChannelEditor()}catch(e){$('error').textContent=e.message}};
 await installSensorExperience();
}
async function saveChannelEditor(){
 const saved=await tool('set_channel_config',{schema_version:1,channels:readChannelDraft()});channelDraft=saved.channels;renderChannelEditor();
 if($('partResult'))$('partResult').textContent='已保存；真实输入和输出已关闭，请按接线情况重新启用。';
 if($('saved'))$('saved').textContent='已保存；真实输入和输出已关闭。';
}
async function simulateSelected(){
 const c=channelDraft.find(c=>c.channel===Number($('channel').value));if(!c)throw Error('请先配置一个输入通道');
 return tool('simulate_channel_input',{channel:c.channel,value:Number($('pressure').value),unit:c.type==='temperature'?'degC':'adc_raw'});
}
async function runVibration(intensity=null){
 if(!$('vibrationChannel').options.length)throw Error('请先添加震动输出通道并保存');
 return tool('set_vibration',{channel:Number($('vibrationChannel').value),intensity:intensity??Number($('intensity').value),duration_ms:intensity===0?1:Number($('duration').value)});
}
async function updateChannelReadings(){
 const d=await tool('read_channel_values');
 if($('values'))$('values').textContent=d.values.map(v=>'CH'+v.channel+' '+v.name+' · '+(channelTypeLabels[v.type]||v.type)+' · '+(v.value==null?'暂无有效值':v.value+' '+v.unit)+' · '+v.source+' / '+v.quality).join('\n');
 const selected=channelDraft.find(c=>c.channel===Number($('channel').value));
 $('press').disabled=!selected||(d.physical_inputs_enabled&&selected.driver!=='simulation');
 $('release').disabled=!selected||selected.type!=='pressure'||$('press').disabled;
 renderDiagnostics(d);
 return d;
}

const diagnosticHistory=new Map();let diagnosticValues=[],sensorExperienceReady=false,diagnosticPolling=false;
function renderDiagnostics(d){
 if(!$('diagnosticCanvas'))return;diagnosticValues=d.values;
 for(const v of d.values){
  const points=diagnosticHistory.get(v.channel)||[];
  if(v.value!=null&&v.quality==='ok'&&(!points.length||points.at(-1).at!==v.uptime_ms||points.at(-1).source!==v.source)){
   points.push({at:v.uptime_ms,value:v.value,source:v.source});if(points.length>120)points.shift();diagnosticHistory.set(v.channel,points);
  }
 }
 const select=$('diagnosticChannel'),previous=select.value;
 if(Array.from(select.options).map(o=>o.value).join(',')!==d.values.map(v=>String(v.channel)).join(',')){
  select.replaceChildren();for(const v of d.values)select.add(new Option('CH'+v.channel+' · '+v.name,v.channel));select.value=previous;if(!select.value&&select.options.length)select.selectedIndex=0;
 }
 for(const option of select.options){const value=d.values.find(v=>String(v.channel)===option.value);if(value)option.textContent='CH'+value.channel+' · '+value.name;}
 drawDiagnostic();
}
function drawDiagnostic(){
 const v=diagnosticValues.find(v=>v.channel===Number($('diagnosticChannel').value));if(!v)return;
 $('diagnosticSummary').textContent='CH'+v.channel+' '+v.name+' · '+(v.value==null?'暂无有效值':v.value+' '+v.unit)+' · '+v.source+' / '+v.quality+(v.type==='pressure'?' · '+(v.calibrating?'校准中':v.active?'按压中':'已释放')+' · 阈值 '+v.release_threshold+' / '+v.press_threshold:'');
 const canvas=$('diagnosticCanvas'),width=canvas.clientWidth,height=canvas.clientHeight,scale=window.devicePixelRatio||1;
 canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
 const ctx=canvas.getContext('2d');ctx.setTransform(scale,0,0,scale,0,0);
 ctx.clearRect(0,0,width,height);const points=diagnosticHistory.get(v.channel)||[];
 let low=v.type==='pressure'?0:Math.min(0,...points.map(p=>p.value)),high=v.type==='pressure'?4095:Math.max(1,...points.map(p=>p.value));
 ctx.fillStyle='#63736a';ctx.font='14px sans-serif';ctx.fillText('最近 120 次有效读数 · '+v.unit,12,18);
 if(points.length<2){ctx.fillText('等待更多有效读数…',12,48);return;}
 const y=n=>height-20-(n-low)/(high-low)*(height-55);
 ctx.strokeStyle='#dce3db';ctx.beginPath();ctx.moveTo(12,height-20);ctx.lineTo(width-12,height-20);ctx.stroke();
 for(let i=1;i<points.length;i++){
  if(points[i].source!==points[i-1].source||points[i].at<points[i-1].at)continue;
  ctx.strokeStyle=points[i].source==='sensor'?'#2b6249':'#996817';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(12+(i-1)*(width-24)/(points.length-1),y(points[i-1].value));ctx.lineTo(12+i*(width-24)/(points.length-1),y(points[i].value));ctx.stroke();
 }
}
function fillCalibrationChannels(){
 const select=$('calibrationChannel'),old=select.value;select.replaceChildren();
 for(const c of channelDraft.filter(c=>c.enabled&&c.type==='pressure'&&c.driver!=='simulation'))select.add(new Option('CH'+c.channel+' · '+c.name,c.channel));
 if(Array.from(select.options).some(o=>o.value===old))select.value=old;
}
const calibrationReasons={capture_all_stages:'请依次采集三个阶段',too_few_samples:'样本不足，请重新采集',light_press_not_separated:'轻按和静置未能区分，请重新采集',baseline_unstable:'静置阶段不稳定，请不要碰传感器',strong_press_below_light:'用力按的数据低于轻按，请重新采集',adc_saturated:'ADC 饱和，请检查接线',ok:'数据有效，可保存阈值'};
const sensorActions=new Set();let latestCalibration=null;
function showCalibration(c){
 latestCalibration=c;
 $('calibrationStatus').textContent=(c.applied?'阈值已保存。':c.capturing?'正在采集，剩余 '+Math.ceil(c.remaining_ms/1000)+' 秒。':calibrationReasons[c.reason]||c.reason)+' '+(c.error||'')+'\n'+c.stages.map(s=>['静置','轻按','用力按'][s.stage]+'：'+s.samples+' 个样本，中位值 '+s.median).join('\n')+(c.press_threshold!=null?'\n推荐：按下 '+c.press_threshold+' / 释放 '+c.release_threshold:'');
 for(const [stage,id] of ['calibrateIdle','calibrateLight','calibrateStrong'].entries())$(id).disabled=sensorActions.has(id)||c.capturing||!$('calibrationChannel').options.length||(stage>0&&(!c.engaged||c.stages[stage-1].samples<20));
 $('applyCalibration').disabled=sensorActions.has('applyCalibration')||!c.ready;
}
async function refreshSensorExperience(){
 const mode=await tool('get_operating_mode');$('operatingStatus').textContent=(mode.mode==='daily'?'已保存日常模式：重启恢复真实输入。':'手动模式：重启关闭真实输入。')+(mode.physical_inputs_enabled?' 当前正在真实采样。':' 当前真实输入关闭。')+' 震动输出不会自动恢复。';
 showCalibration(await tool('get_pressure_calibration'));
}
async function installSensorExperience(){
 if(sensorExperienceReady){fillCalibrationChannels();return;}
 const section=document.createElement('section');section.id='sensorExperience';
 section.innerHTML='<h2>日常使用与压力校准</h2><p id="operatingStatus"></p><label><input id="dailyConfirmed" type="checkbox">我已安装主板和传感器，允许重启恢复真实输入</label><button id="dailyMode">保存日常模式</button><button id="manualMode">恢复手动模式</button><p>校准前启用真实输入，安装到玩偶内后逐路校准；校准期间本通道暂停触摸事件。保持对应姿势点击按钮，每阶段采集约 3 秒。无效数据不会保存；60 秒无操作自动退出。</p><select id="calibrationChannel" aria-label="校准压力通道"></select><button id="calibrateIdle">1. 静置采集</button><button id="calibrateLight">2. 轻按采集</button><button id="calibrateStrong">3. 用力按采集</button><pre id="calibrationStatus"></pre><button id="applyCalibration" disabled>保存推荐阈值</button><button id="cancelCalibration">取消校准</button><h2>实时通道诊断</h2><select id="diagnosticChannel" aria-label="诊断通道"></select><p id="diagnosticSummary"></p><canvas id="diagnosticCanvas" width="720" height="190" style="width:100%;height:190px" aria-label="通道数值曲线"></canvas><p id="diagnosticConnection">绿色是真实采样，棕色是模拟；曲线为等间距采样点，不是牛顿或时间标定曲线。</p>';
 $('parts').closest('section').after(section);fillCalibrationChannels();
 const action=(id,fn)=>{$(id).onclick=async()=>{if(sensorActions.has(id))return;sensorActions.add(id);try{$(id).disabled=true;$('error').textContent='';await fn();await refreshSensorExperience()}catch(e){$('error').textContent=e.message}finally{sensorActions.delete(id);if(latestCalibration)showCalibration(latestCalibration);if(!id.startsWith('calibrate')&&id!=='applyCalibration')$(id).disabled=false}}};
 action('dailyMode',async()=>{if(!$('dailyConfirmed').checked)throw Error('请先确认传感器已经安装');await tool('set_operating_mode',{mode:'daily',hardware_confirmed:true});$('physical').checked=true;$('outputEnabled').checked=false});
 action('manualMode',async()=>{await tool('set_operating_mode',{mode:'manual'});$('physical').checked=false;$('dailyConfirmed').checked=false;$('outputEnabled').checked=false});
 for(const [stage,id] of ['calibrateIdle','calibrateLight','calibrateStrong'].entries())action(id,()=>tool('capture_pressure_calibration',{channel:Number($('calibrationChannel').value),stage,duration_ms:3000}));
 action('applyCalibration',async()=>{await tool('apply_pressure_calibration');channelDraft=(await tool('get_channel_config')).channels;renderChannelEditor()});
 action('cancelCalibration',()=>tool('cancel_pressure_calibration'));
 $('diagnosticChannel').onchange=drawDiagnostic;
 try{await refreshSensorExperience();sensorExperienceReady=true;}catch(e){$('operatingStatus').textContent='当前固件尚未提供校准与日常模式，请升级到 v2.3。';return;}
 setInterval(async()=>{if(diagnosticPolling)return;diagnosticPolling=true;try{await updateChannelReadings();await refreshSensorExperience();$('diagnosticConnection').textContent='诊断连接正常 · 绿色：真实采样；棕色：模拟。';}catch(e){$('diagnosticConnection').textContent='诊断连接中断，曲线保留之前的读数。';}finally{diagnosticPolling=false}},750);
}
