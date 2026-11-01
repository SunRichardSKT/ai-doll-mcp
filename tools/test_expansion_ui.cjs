// Production editor, isolated RPC fixture; no device or saved settings touched.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8');
 const html=source.split('R"HTML(')[1].split(')HTML";')[0].replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.setContent(html);
  await page.evaluate(()=>{
   window.$=id=>document.getElementById(id);window.requests=[];
   window.tool=async(name,args)=>{requests.push({name,args});if(name==='set_channel_config')return {channels:args.channels};if(name==='set_light')return {values:[]};throw Error('Unexpected fixture tool '+name)};
  });
  await page.addScriptTag({path:path.join(root,'tools/channel_editor.js')});
  await page.evaluate(()=>{
   channelCapabilities={max_channels:16,port_state_model:'per_port_v1',types:[{type:'pressure',drivers:['simulation','mux_adc']},{type:'temperature',drivers:['simulation','ds18b20']},{type:'motion',drivers:['simulation','lis3dh']},{type:'vibration',drivers:['simulation','gpio_pwm']},{type:'light',drivers:['simulation','gpio_pwm']},{type:'switch',drivers:['simulation','gpio_switch']}]};
   channelDraft=Array.from({length:8},(_,i)=>({channel:i,name:'触摸'+i,type:'pressure',driver:'mux_adc',mux_port:i,mode:'connected',enabled:true,options:{press_threshold:699+i,release_threshold:295+i}}));window.original=JSON.stringify(channelDraft);renderChannelEditor();
  });
  for(const kind of ['motion','light','switch']){await page.selectOption('#expansionType',kind);await page.click('#addExpansion');}
  let draft=await page.evaluate(()=>readChannelDraft());assert.deepEqual(draft.slice(0,8),JSON.parse(await page.evaluate(()=>original)));
  assert.deepEqual(draft.slice(8).map(c=>[c.channel,c.type,c.mode,c.enabled]),[[8,'motion','off',false],[9,'light','off',false],[10,'switch','off',false]]);
  assert.equal(draft[8].address,24);assert.equal(draft[9].gpio,20);assert.equal(draft[10].gpio,21);
  await page.evaluate(()=>saveChannelEditor());
  const saved=await page.evaluate(()=>requests.find(r=>r.name==='set_channel_config').args.channels);assert.deepEqual(saved,draft);
  await page.evaluate(()=>{channelDraft.find(c=>c.type==='light').mode='simulation';channelDraft.find(c=>c.type==='light').enabled=true;renderChannelEditor();$('lightTest').open=true;});
  await page.click('#tryLight');await page.click('#stopLight');
  assert.deepEqual(await page.evaluate(()=>requests.filter(r=>r.name==='set_light').map(r=>r.args.brightness)),[20,0]);
  await page.evaluate(()=>{document.querySelector('#driver8').closest('details').open=true;});
  await page.selectOption('#driver8','simulation');await page.selectOption('#driver8','lis3dh');assert.equal(await page.inputValue('#binding8'),'24');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
  await page.screenshot({path:path.join(root,'build/current-board-software/expansion-settings.png'),fullPage:true});
  await page.locator('#expansionControls').screenshot({path:path.join(root,'build/current-board-software/expansion-controls.png')});
  await page.evaluate(()=>{
   channelCapabilities={max_channels:16,physical_outputs_supported:false,types:[{type:'pressure',drivers:['simulation','mux_adc','gpio_adc']},{type:'switch',drivers:['simulation','gpio_switch']}]};
   document.getElementById('expansionControls').remove(); // New firmware page starts without the old device's controls.
   channelDraft=channelDraft.filter(c=>c.type==='pressure');renderChannelEditor();
  });
  assert.deepEqual(await page.locator('#expansionType option').evaluateAll(nodes=>nodes.map(n=>n.value)),['switch']);
  assert.equal(await page.locator('#lightTest').isVisible(),false);
  assert.equal(await page.locator('#vibrationChannel').isVisible(),false);
  assert.deepEqual(await page.locator('#type0 option').evaluateAll(nodes=>nodes.map(n=>n.value)),['pressure','switch']);
  console.log('PASS pressure/switch-only capability filtering: removed sensors and physical outputs hidden.');
  console.log('PASS expansion editor: 8 original thresholds preserved, safe off defaults, address/GPIO round trip, LED test/stop, 390px layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
