// Actual shared editor on a 390px phone viewport; RPC is an isolated fixture.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8');
 const html=source.split('R"HTML(')[1].split(')HTML";')[0].replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.setContent(html);
  await page.evaluate(()=>{window.$=id=>document.getElementById(id);window.requests=[];window.tool=async(name,args)=>{requests.push({name,args});if(name==='set_channel_config')return {channels:args.channels};throw Error(name);};});
  await page.addScriptTag({path:path.join(root,'tools/channel_editor.js')});
  await page.evaluate(()=>{
   channelCapabilities={max_channels:16,port_state_model:'per_port_v1',physical_outputs_supported:false,types:[{type:'pressure',drivers:['mux_adc','gpio_adc','simulation']},{type:'temperature',drivers:['mux_adc','gpio_adc','simulation']},{type:'wetness',drivers:['mux_adc','gpio_adc','simulation']},{type:'switch',drivers:['gpio_switch','simulation']}]};
   channelDraft=Array.from({length:8},(_,i)=>({channel:i,name:'部位'+i,type:'pressure',driver:'mux_adc',mux_port:i,mode:'connected',enabled:true,options:{press_threshold:699+i,release_threshold:295+i}}));window.before=JSON.stringify(channelDraft);renderChannelEditor();
  });
  for(const [ch,type] of [[6,'temperature'],[7,'wetness']]){
   await page.locator('#type'+ch).evaluate(el=>{el.closest('details').open=true;});
   await page.selectOption('#type'+ch,type);
   assert.equal(await page.inputValue('#driver'+ch),'mux_adc');assert.equal(await page.inputValue('#binding'+ch),String(ch));
   assert.equal(await page.inputValue('#portMode'+ch),'off');
  }
  const draft=await page.evaluate(()=>readChannelDraft()),before=JSON.parse(await page.evaluate(()=>before));
  assert.deepEqual(draft.slice(0,6),before.slice(0,6));assert.equal(draft[6].options.beta,3435);assert.equal(draft[6].options.series_ohm,4700);
  assert.equal(draft[7].options.hold_ms,600);assert.equal(draft[7].options.pressure_channel,0);
  await page.evaluate(()=>saveChannelEditor());assert.deepEqual(await page.evaluate(()=>requests[0].args.channels),draft);
  assert.equal(await page.locator('#lightTest').isVisible(),false);assert.deepEqual(errors,[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(root,'build/resistive-settings.png'),fullPage:true});
  console.log('PASS NTC/wet-pad conversion: physical port retained, safe off defaults, six original calibrations preserved, 390px layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
