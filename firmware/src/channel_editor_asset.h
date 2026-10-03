#pragma once
// Generated from tools/channel_editor.js; edit that source.
static const char CHANNEL_EDITOR_JS[] PROGMEM=R"CHANNEL_JS(// Shared by the ESP32 portal and the computer page; labels are always rendered as text.
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
}
async function loadChannels(){
 channelCapabilities=await tool('get_channel_capabilities');channelDraft=(await tool('get_channel_config')).channels;renderChannelEditor();
 $('addChannel').onclick=()=>{try{channelDraft=readChannelDraft();const id=Array.from({length:channelCapabilities.max_channels},(_,i)=>i).find(i=>!channelDraft.some(c=>c.channel===i));if(id===undefined)throw Error('已达到逻辑通道上限');channelDraft.push({channel:id,name:'CH'+id,type:'pressure',driver:'simulation',enabled:true,options:{}});channelDraft.sort((a,b)=>a.channel-b.channel);renderChannelEditor()}catch(e){$('error').textContent=e.message}};
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
 return d;
}
)CHANNEL_JS";
