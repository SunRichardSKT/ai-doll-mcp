// Shared desktop/server editor; saving changes only combination preferences.
window.DollBodyCombinations={mount(section,call,channels,preferences){
 section.id='bodyCombinations';
 section.innerHTML='<h2>多个部位组合</h2><p>选择至少两个压力部位，1.5秒内按下且同时保持，按动作名称提供给 AI。原始记录保留。</p><div id="comboList"></div><label>动作名称<input id="comboName" maxlength="40" value="拥抱"></label><div id="comboPorts"></div><button id="saveCombo">添加组合</button><p id="comboResult" role="status"></p>';
 let rules=preferences.body_combinations||[],busy=false;
 const el=id=>section.querySelector('#'+id);
 for(const c of channels.filter(c=>c.type==='pressure'&&c.mode!=='off')){
  const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=c.channel;
  label.append(input,document.createTextNode('CH'+c.channel+' · '+c.name));el('comboPorts').append(label);
 }
 async function save(next){
  if(busy)return;busy=true;section.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{
   const result=await call('update_companion_preferences',{changes:{body_combinations:next}});
   rules=result.preferences.body_combinations;render();el('comboResult').textContent='组合已保存。';
  }catch(e){el('comboResult').textContent=e.message;}
  finally{busy=false;section.querySelectorAll('button').forEach(b=>b.disabled=false);}
 }
 function render(){
  el('comboList').replaceChildren();
  for(const r of rules){
   const row=document.createElement('p'),label=document.createElement('span'),button=document.createElement('button');
   label.textContent=r.name+'：'+r.channels.map(c=>channels.find(x=>x.channel===c)?.name||'CH'+c).join('＋');
   button.textContent='删除';button.onclick=()=>save(rules.filter(x=>x.name!==r.name));
   row.append(label,button);el('comboList').append(row);
  }
 }
 el('saveCombo').onclick=()=>save([...rules,{name:el('comboName').value,channels:[...el('comboPorts').querySelectorAll('input:checked')].map(x=>Number(x.value)),window_ms:1500}]);
 render();
}};
