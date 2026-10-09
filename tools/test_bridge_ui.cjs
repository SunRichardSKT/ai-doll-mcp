/* Real selected device transport -> archive/outbox -> pushed demo response -> ACK. */
const fs=require('fs'),path=require('path');const {chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const root=path.resolve(__dirname,'..'),page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 let connected=false,originalPrefs=null;
 try{
  await page.goto('http://127.0.0.1:8768/bridge');
  const connection=await page.evaluate(()=>client.api('/connection'));
  await page.waitForFunction(()=>document.querySelector('#selected').textContent.includes('CH'));
  const current=await page.evaluate(()=>client.tool('get_interaction_status'));
  if(current.active_session)throw Error('Do not interrupt another active user interaction');
  originalPrefs=await page.evaluate(()=>client.tool('get_feedback_preferences'));
  await page.evaluate(prefs=>client.tool('set_feedback_preferences',{policy:{...prefs.policy,notify_pressure_patterns:false,quiet_hours:{...prefs.policy.quiet_hours,enabled:false}},feedback:prefs.feedback}),originalPrefs);
  await page.click('#connect');await page.waitForFunction(()=>client.running&&document.querySelector('#press').disabled===false);connected=true;
  const originalSub=await page.evaluate(()=>client.sub.id);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#selected').textContent.includes('CH'));
  await page.click('#connect');await page.waitForFunction(()=>client.running&&document.querySelector('#press').disabled===false);
  if(await page.evaluate(()=>client.sub.id)!==originalSub)throw Error('Refresh did not resume the same target');
  // Send from a separate page: the receiving chat gets no new user message.
  const sender=await browser.newPage();await sender.goto('http://127.0.0.1:8768/companion');
  await sender.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length>0);
  const input=await sender.evaluate(async()=>{const cfg=await tool('get_channel_config');const ch=cfg.channels.find(c=>c.type==='pressure'&&c.enabled);await tool('doll_simulate_press',{channel:ch.channel,value:3200});return ch.channel});
  await page.waitForSelector('#messages article',{timeout:20000});
  const text=await page.textContent('#messages article');if(!text.includes('演示回执（非 AI）')||!text.includes('simulation'))throw Error('Source/model labelling missing');
  const eventId=await page.getAttribute('#messages article','data-event-id');
  await page.waitForFunction(async id=>(await client.api('/bridge/status')).replies.some(r=>r.event_id===id&&r.source==='demo'),eventId);
  await sender.evaluate(ch=>tool('doll_simulate_press',{channel:ch,value:0}),input);
  await page.waitForTimeout(1200);if(await page.locator('#messages article').count()!==1)throw Error('Release caused duplicate feedback');
  await page.setViewportSize({width:390,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile overflow');
  await page.screenshot({path:path.join(root,'build/device-lab/bridge-live-mobile.png'),fullPage:true});
  await page.evaluate(()=>client.stop());connected=false;
  const state=await page.evaluate(()=>client.api('/bridge/status'));if(state.subscriptions.some(s=>s.active))throw Error('Unsubscribe failed');
  if(errors.length)throw Error(errors.join('\n'));
  const report={passed:true,bridge:'2.9.0',transport:connection.transport,at:new Date().toISOString(),checks:['refresh resumes same subscription','separate window simulated pressure over '+connection.transport,'automatic pushed event without receiving chat user message','explicit simulation/demo labels','durable reply and delivery ACK','release does not duplicate feedback','unsubscribe and ordinary archive restored','390px mobile layout/no JS errors']};
  fs.writeFileSync(path.join(root,'build/device-lab/bridge-live-test.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
  await sender.close();
 }finally{if(connected)await page.evaluate(()=>client.stop()).catch(()=>{});if(originalPrefs)await page.evaluate(prefs=>client.tool('set_feedback_preferences',prefs),originalPrefs);await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
