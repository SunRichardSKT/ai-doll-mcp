/* Real ESP32 -> direct server -> idle browser callback. The host/model are test
 * callbacks, explicitly demo; this is not a model provider or a new chat UI. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const cfg=JSON.parse(fs.readFileSync(process.env.DOLL_DIRECT_TEST_CONFIG||path.join(root,'build/direct-device-test/frontend-private.json'),'utf8'));
const base='/d/'+cfg.device_id;
const output=path.join(root,'build/direct-device-test');
async function api(route,data){
 const response=await fetch(cfg.server+route,{method:data===undefined?'GET':'POST',headers:{Authorization:'Bearer '+cfg.admin_token,'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 const result=await response.json();if(!response.ok)throw Error(result.error);return result;
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(cfg.server);await page.locator('#adminToken').fill(cfg.admin_token);await page.locator('#connectForm button').click();
  await page.locator('#workspace').waitFor({state:'visible'});await page.locator('#devices a').first().waitFor();
  await page.screenshot({path:path.join(output,'server-mobile.png'),fullPage:true});
  await page.goto(cfg.server+base+'/companion');
  await page.locator('#part0').waitFor();
  const originalName=await page.locator('#part0').inputValue();assert(originalName.length>0);
  // Exercise real remote persistence through a phone-sized page. Preserve the
  // original channel map and only resave its current values.
  await page.locator('#saveParts').click();
  await page.waitForFunction(()=>document.getElementById('saved')?.textContent.includes('保存'),null,{timeout:16000});
  await page.locator('#persona').fill('接口验收用人设；测试结束不代表真实模型响应。');await page.locator('#savePersona').click();
  await page.screenshot({path:path.join(output,'settings-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  await page.addScriptTag({url:cfg.server+'/bridge-client.js'});await page.addScriptTag({url:cfg.server+'/conversation-queue.js'});
  await page.evaluate(async base=>{
   window.originalChat={id:'existing-frontend-acceptance',messages:[{role:'user',text:'原聊天上下文'}],callbackCount:0};
   const queue=new DollConversationQueue();
   window.testBridge=new DollBridgeClient({baseUrl:base,targetId:originalChat.id,
    runDelivery:(op,opts)=>queue.run(originalChat.id,op,opts),
    onInteraction:async event=>{originalChat.callbackCount++;originalChat.event=event;return {text:'原聊天生成回调测试替身，收到 '+event.data.events[0].body_part,source:'demo'}},
    onReply:(answer,event)=>originalChat.messages.push({role:'assistant',text:answer.text,eventId:event.eventId})});
   await testBridge.start({duration_sec:60,ttl_sec:60});
  },base);
  await api(base+'/companion/tool',{name:'doll_simulate_press',arguments:{channel:0,value:3200}});
  await page.waitForFunction(()=>window.originalChat.messages.length===2,null,{timeout:15000});
  const result=await page.evaluate(()=>({callbacks:originalChat.callbackCount,target:testBridge.target,
   source:originalChat.event.data.events[0].source,part:originalChat.event.data.events[0].body_part,
   originalContextPreserved:originalChat.messages[0].text==='原聊天上下文',newUserMessages:0}));
  assert.equal(result.callbacks,1);assert.equal(result.source,'simulation');assert(result.originalContextPreserved);
  await page.evaluate(()=>testBridge.stop());
  await new Promise(resolve=>setTimeout(resolve,5500));
  assert.equal(await page.evaluate(()=>originalChat.callbackCount),1);
  const report={passed:true,real_device:true,collector_required:false,idle_frontend_callback:true,
    mobile_server_management:true,remote_channel_save:true,session_stop:true,...result,
    model_callback:'test_double_demo',real_model_verified:false,browser_errors:errors};
  fs.writeFileSync(path.join(output,'frontend-report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
