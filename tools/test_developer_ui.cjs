/* Actual editor/portal markup with isolated API fixtures; never writes a real device. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const channels=[{channel:0,name:'头顶',type:'pressure',driver:'mux_adc',mux_port:0,mode:'connected',enabled:true,options:{press_threshold:699,release_threshold:295}},
 {channel:1,name:'手',type:'pressure',driver:'mux_adc',mux_port:1,mode:'off',enabled:false,options:{press_threshold:900,release_threshold:300}}];
const storage={available:true,pending_records:0,max_records:256,lost_records:0,corrupt_records:0,write_failures_since_boot:0,clock_synced:true};
const calibration=()=>({capturing:false,engaged:false,ready:false,reason:'capture_all_stages',stages:[0,1,2].map(stage=>({stage,samples:0,median:0}))});
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const output=path.join(root,'build/developer-ui');fs.mkdirSync(output,{recursive:true});
 try{
  for(const kind of ['computer','device','channels-embed','developer-embed']){
   const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[],calls=[];
   let connected=true,address='192.168.1.50',capture=calibration(),readSerial=0;
   page.on('pageerror',e=>errors.push(e.message));
   function status(){return {device_id:'fixture-device',hostname:'ai-doll-112233445566.local',sensor_mode:'sensor',wifi_connected:connected,ip:connected?address:'0.0.0.0',ssid:'fixture',network_mode:connected?'normal':'recovery',ap_ip:'192.168.4.1',ap_ssid:'fixture-device',config_ap_open:true,event_storage:storage};}
   function tool(name,args){calls.push({name,args});switch(name){
    case 'get_channel_capabilities':return {port_state_model:'per_port_v1',max_channels:16,types:[{type:'pressure',drivers:['mux_adc','simulation']},{type:'temperature',drivers:['simulation']},{type:'vibration',drivers:['simulation']}]};
    case 'get_channel_config':return {channels,port_state_model:'per_port_v1'};
    case 'set_channel_state':Object.assign(channels[args.channel],args,{enabled:args.mode!=='off'});return {channels,port_state_model:'per_port_v1'};
    case 'get_operating_mode':return {mode:'daily',physical_inputs_enabled:true};
    case 'get_pressure_calibration':return capture;
    case 'capture_pressure_calibration':capture={...calibration(),capturing:true,remaining_ms:3000};return capture;
    case 'read_channel_values':return {physical_inputs_enabled:true,physical_outputs_enabled:false,values:[{channel:0,name:'头顶',type:'pressure',value:32,unit:'adc_raw',source:'sensor',quality:'ok',uptime_ms:++readSerial,release_threshold:295,press_threshold:699}]};
    case 'get_sensor_config':return {enabled:true,raw:[32]};
    case 'get_touch_events':return {boot_id:'fixture',events:[{channel:0,source:'sensor',phase:'press',value:800}],next_cursor:1};
    case 'doll_get_status':return status();
    case 'get_event_storage_status':return storage;
    case 'get_persona':return {persona:''};
    case 'query_device_history':return {events:[],notices:[],next_cursor:0,has_more:false};
    default:throw Error('Unexpected fixture tool '+name);
   }}
   await page.route('http://fixture/**',async route=>{
    const request=route.request(),p=new URL(request.url()).pathname;let body,type='application/json',code=200;
    if(p==='/'||p==='/companion'){
     body=kind==='device'?fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8').split('R"HTML(')[1].split(')HTML"')[0]:fs.readFileSync(path.join(root,'tools/companion.html'),'utf8');type='text/html';
    }else if(p==='/channel-editor.js'||p==='/console-embed.js'){body=fs.readFileSync(path.join(root,'tools',p==='/channel-editor.js'?'channel_editor.js':'console_embed.js'),'utf8');type='application/javascript';}
    else if(p.endsWith('.js')){body='/* Unrelated history, OTA and persona UI excluded from this fixture. */';type='application/javascript';}
    else if(p==='/api/setup')body=JSON.stringify({token:'fixture',enabled:true,auth_enabled:false});
    else if(p==='/api/uplink')body=JSON.stringify({enabled:false});
    else if(p==='/api/status')body=JSON.stringify(status());
    else if(p==='/connection')body=JSON.stringify({transport:'wifi',device_host:address,device_ip:connected?address:null});
    else if(p==='/companion/state')body=JSON.stringify({active_session:null,last_sync:Date.now()/1000});
    else if(p==='/companion/tool'){const data=request.postDataJSON();body=JSON.stringify(tool(data.name,data.arguments));}
    else if(p==='/api/tool'){const {name,arguments:args}=request.postDataJSON().params;body=JSON.stringify({result:{content:[{type:'text',text:JSON.stringify(tool(name,args))}]}});}
    else {body='{}';code=404;}
    await route.fulfill({status:code,contentType:type,body});
   });
   const panel=kind==='channels-embed'?'?panel=channels':kind==='developer-embed'?'?panel=simulation':'';
   await page.goto('http://fixture/'+(kind==='device'?'':'companion')+panel);
   await page.locator('#operatingStatus').waitFor({state:'attached'});await page.waitForFunction(()=>document.getElementById('operatingStatus').textContent.includes('已接入'));
   const count=name=>calls.filter(c=>c.name===name).length;
   assert.equal(await page.locator('#press').isVisible(),false,kind+' hides simulation by default');
   if(kind!=='developer-embed'){
    assert.equal(await page.locator('#physical').isVisible(),false,kind+' redundant global input control is hidden');
    assert.equal(await page.locator('#dailyMode').count(),0,kind+' ambiguous daily mode is removed');
    const other=JSON.stringify(channels[1]),thresholds=JSON.stringify(channels[0].options);
    await page.selectOption('#portMode0','simulation');await page.click('#savePort0');
    await page.waitForFunction(()=>document.getElementById('portMode0').value==='simulation'&&!document.getElementById('savePort0').disabled);
    assert.equal(channels[0].mode,'simulation');
    await page.selectOption('#portMode0','connected');await page.click('#savePort0');
    await page.waitForFunction(()=>document.getElementById('portMode0').value==='connected'&&!document.getElementById('savePort0').disabled);
    assert.equal(JSON.stringify(channels[1]),other);assert.equal(JSON.stringify(channels[0].options),thresholds);
    assert.equal(await page.locator('#calibrateIdle').isVisible(),true,kind+' calibration remains available');
   }
   const initial=count('read_channel_values');await page.waitForTimeout(1750);
   assert.equal(count('read_channel_values'),initial,kind+' closed developer controls do not poll readings');
   if(kind==='channels-embed'){
    // Hidden developer section must never issue debug reads even if opened by script.
    await page.evaluate(()=>{document.getElementById('developerOptions').open=true;document.getElementById('debugReadings').open=true;});
    await page.waitForTimeout(1700);assert.equal(count('read_channel_values'),initial);
   }else{
    await page.locator('#developerOptions>summary').click();
    for(const [id,name,target]of [['debugReadings','read_channel_values','#values'],['debugEvents','get_touch_events','#debugEventsData'],['debugConfig','get_channel_config','#debugConfigData'],['debugDevice','doll_get_status','#debugDeviceData']]){
     const previous=count(name);await page.locator('#'+id+'>summary').click();
     await page.waitForFunction(selector=>document.querySelector(selector).textContent.length>0,target);
     assert.ok(count(name)>previous,kind+' '+id+' refreshes when opened');
     await page.locator('#'+id+'>summary').click();await page.waitForTimeout(300);const closed=count(name);
     await page.waitForTimeout(1650);assert.equal(count(name),closed,kind+' '+id+' stops reads when closed');
    }
    await page.locator('#debugDevice>summary').click();await page.waitForTimeout(200);
    await page.locator('#developerOptions>summary').click();await page.waitForTimeout(200);
    const parentClosed=count('doll_get_status');await page.waitForTimeout(1650);
    assert.equal(count('doll_get_status'),parentClosed,kind+' closing developer group stops its open child window');
   }
   if(kind!=='developer-embed'){
    await page.click('#calibrateIdle');await page.waitForFunction(()=>document.getElementById('calibrationReadings').textContent.includes('sensor'));
    assert.equal(count('capture_pressure_calibration'),1);assert.equal(calls.find(c=>c.name==='capture_pressure_calibration').args.channel,0);
    capture=calibration();
   }
   if(kind==='device'){
    assert.equal(await page.textContent('#deviceName'),'ai-doll-112233445566.local');
    assert.equal(await page.getAttribute('#deviceName','href'),'http://ai-doll-112233445566.local/');
    assert.ok((await page.textContent('#serverStatus')).includes('Operit 手机直接读取'));
    assert.equal(await page.textContent('#deviceIP'),address);assert.equal(await page.getAttribute('#deviceIP','href'),'http://'+address+'/');
    connected=false;await page.waitForFunction(()=>document.getElementById('deviceIP').textContent==='未连接');
    assert.equal(await page.getAttribute('#deviceIP','href'),null,'offline IP is not clickable');
    connected=true;address='192.168.1.51';await page.waitForFunction(ip=>document.getElementById('deviceIP').textContent===ip,address);
   }
   assert.equal(calls.some(c=>['set_channel_config','apply_pressure_calibration','set_output_enabled','simulate_channel_input','acknowledge_events','acknowledge_chat_context'].includes(c.name)),false,kind+' diagnostic reads do not write or consume');
   await page.setViewportSize({width:390,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false,kind+' mobile layout');
   await page.screenshot({path:path.join(output,kind+'.png'),fullPage:true});assert.deepEqual(errors,[]);
   await page.close();console.log('PASS '+kind+': real controls/calibration, collapsed debug polling, isolated read-only windows, mobile layout. Fixture only.');
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
