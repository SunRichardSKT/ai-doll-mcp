// Actual shared editor on a 390px phone viewport; RPC is an isolated fixture.
const path=require('node:path'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const {source}=require('./firmware_test_assets.cjs');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const html=source('device_page').replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.setContent(html);
  await page.evaluate(()=>{
   window.$=id=>document.getElementById(id);window.writes=[];
   window.tool=async(name,args)=>{
    if(name==='get_pressure_calibration')return {engaged:false,capturing:false,ready:false,reason:'capture_all_stages',stages:[]};
    if(name==='read_channel_values'){
     if(window.disconnected)throw Error('offline');
     return {physical_inputs_enabled:true,values:[{channel:6,type:'temperature',unit:'degC',source:'sensor',mode:'connected',...window.sample}]};
    }
    if(name==='get_channel_config')return {channels:window.stored};
    if(name==='set_channel_config')window.stored=args.channels;
    else if(name==='set_channel_state'){
     const row=window.stored.find(c=>c.channel===args.channel);Object.assign(row,args);row.enabled=row.mode!=='off';
    }else throw Error(name);
    window.writes.push({name,args});return {channels:JSON.parse(JSON.stringify(window.stored))};
   };
  });
  await page.addScriptTag({content:source('channel_editor')});
  await page.evaluate(()=>{
   channelCapabilities={max_channels:16,port_type_update:true,port_state_model:'per_port_v1',physical_outputs_supported:false,types:[{type:'pressure',drivers:['mux_adc','gpio_adc','simulation']},{type:'temperature',drivers:['mux_adc','gpio_adc','simulation']},{type:'wetness',drivers:['mux_adc','gpio_adc','simulation']},{type:'switch',drivers:['gpio_switch','simulation']}]};
   channelDraft=Array.from({length:8},(_,i)=>({channel:i,name:'部位'+i,type:'pressure',driver:'mux_adc',mux_port:i,mode:i===6?'off':'connected',enabled:i!==6,options:{press_threshold:699+i,release_threshold:295+i}}));
   Object.assign(channelDraft[5],{type:'temperature',options:{model:'ntc',r25_ohm:10000,beta:3435,offset_c:1.25}});
   window.stored=JSON.parse(JSON.stringify(channelDraft));renderChannelEditor();
  });
  await page.evaluate(()=>installSensorExperience());
  const before=await page.evaluate(()=>stored);
  async function save(ch){
   await page.click('#savePort'+ch);
   await page.waitForFunction(n=>document.getElementById('portResult'+n).textContent==='已保存',ch);
  }
  await page.fill('#part7','右手掌');
  await page.selectOption('#type7','wetness');assert.equal(await page.inputValue('#portMode7'),'connected');
  await page.selectOption('#type6','temperature');
  await page.fill('#part6','左手掌');await page.selectOption('#portMode6','connected');await save(6);
  const edited=await page.evaluate(()=>stored),call=await page.evaluate(()=>writes[0]);
  assert.equal(call.name,'set_channel_state');assert.equal(call.args.type,'temperature');
  assert.equal(edited[6].options.beta,3950);assert.equal(edited[6].options.series_ohm,4700);
  assert.equal(edited[6].mux_port,6);assert.equal(edited[6].name,'左手掌');assert.equal(edited[6].mode,'connected');
  assert.deepEqual(edited.filter(c=>c.channel!==6),before.filter(c=>c.channel!==6));
  assert.equal(await page.inputValue('#part7'),'右手掌');assert.equal(await page.inputValue('#type7'),'wetness');
  await page.fill('#part6','左手');await page.press('#part6','Enter');
  assert.deepEqual(await page.evaluate(()=>writes.at(-1).args),{channel:6,name:'左手'});
  const temp=page.locator('#temperatureReading6');
  await page.evaluate(()=>{window.sample={quality:'ok',value:25};});
  await page.waitForFunction(()=>document.getElementById('temperatureReading6').textContent==='25.0 ℃');
  assert.equal(await temp.innerText(),'25.0 ℃');
  await page.evaluate(()=>{window.sample={quality:'probe_open_short_or_out_of_range',value:null};});
  await page.waitForFunction(()=>document.getElementById('temperatureReading6').textContent.includes('检查探头'));
  assert.match(await temp.innerText(),/检查探头/);
  await page.evaluate(()=>{window.disconnected=true;});
  await page.waitForFunction(()=>document.getElementById('temperatureReading6').textContent.includes('连接中断'));
  await page.evaluate(()=>{window.disconnected=false;});
  assert.match(await temp.innerText(),/连接中断/);
  await page.getByRole('button',{name:'使用 10K B3950',exact:true}).click();await save(5);
  assert.equal(await page.evaluate(()=>stored[5].options.offset_c),1.25);assert.equal(await page.evaluate(()=>stored[5].options.beta),3950);
  await page.evaluate(()=>{channelCapabilities.port_type_update=false;stored[0].options.press_threshold=1234;});
  await save(7);const legacy=await page.evaluate(()=>writes.at(-1));
  assert.equal(legacy.name,'set_channel_config');assert.equal(legacy.args.channels[0].options.press_threshold,1234);
  assert.equal(legacy.args.channels[7].options.pressure_channel,0);
  assert.equal(await page.locator('#lightTest').isVisible(),false);assert.deepEqual(errors,[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(root,'build/resistive-settings.png'),fullPage:true});
  console.log('PASS B3950 per-port setup, rename, migration, live/fault values, other drafts and calibrations, older firmware and 390px layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
