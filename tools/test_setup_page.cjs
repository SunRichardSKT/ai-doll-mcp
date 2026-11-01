// Exact source/gzip page; browser and HTTP fixtures do not represent a real iPhone.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const {source}=require('./firmware_test_assets.cjs'),root=path.resolve(__dirname,'..');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{
  for(const colorScheme of ['light','dark']){
   const page=await browser.newPage({viewport:{width:390,height:844},colorScheme}),errors=[],calls=[];
   let online=false,unreachable=false;const token='test_setup_pairing_credential';
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('http://192.168.4.1/**',async route=>{
    const request=route.request(),p=new URL(request.url()).pathname;
    if(p==='/wifi-feedback.js')return route.fulfill({contentType:'application/javascript',body:source('wifi_feedback')});
    if(p==='/setup')return route.fulfill({contentType:'text/html',body:source('setup_page')});
    calls.push({p,headers:request.headers(),body:request.postData()});
    if(unreachable)return route.abort('failed');
    let data;
    if(p==='/api/identity'){assert.equal(request.headers()['x-setup-token']||'','');data={device_id:'fixture-device'};}
    else if(p==='/api/setup')data={token,enabled:true};
    else {assert.equal(request.headers()['x-setup-token'],token);
     if(p==='/api/status')data={device_id:'fixture-device',device_name:'测试娃娃',hostname:'ai-doll-001122334455.local',wifi_connected:online,ip:online?'192.168.1.50':'0.0.0.0',ssid:'home',network_mode:'CONNECTING'};
     else if(p==='/api/scan')data={scanning:false,networks:[{ssid:'home',rssi:-50},{ssid:'<img src=x onerror=alert(1)>',rssi:-60}]};
     else if(p==='/api/wifi'){const args=JSON.parse(request.postData());assert.equal(args.ssid,'home');assert.equal(args.password,'password123');online=true;data={ok:true};}
     else throw Error('Unexpected API '+p);
    }
    return route.fulfill({json:data});
   });
   await page.goto('http://192.168.4.1/setup');await page.waitForFunction(()=>!document.getElementById('scan').disabled);
   const entry=await page.inputValue('#entry');assert.ok(entry.startsWith('http://ai-doll-001122334455.local/setup#'));
   assert.ok(entry.includes(token));assert.ok(entry.includes('device_id=fixture-device'));
   assert.equal(await page.locator('#openDevice').isVisible(),false);
   await page.click('#scan');await page.selectOption('#networks','home');assert.equal(await page.inputValue('#ssid'),'home');
   await page.fill('#password','123');await page.click('#join');assert.match(await page.textContent('#joinResult'),/至少8/);assert.equal(calls.filter(c=>c.p==='/api/wifi').length,0);
   await page.fill('#password','password123');await page.click('#join');await page.evaluate(()=>refresh());
   await page.waitForFunction(()=>document.getElementById('familyIP').textContent.includes('192.168.1.50'));
   assert.equal(await page.inputValue('#password'),'');assert.equal(calls.filter(c=>c.p==='/api/wifi').length,1);
   assert.equal(await page.locator('#openDevice').getAttribute('href'),entry);
   assert.ok((await page.locator('#advanced').getAttribute('href')).includes('/settings#setup_token='));
   await page.click('#copyEntry');assert.match(await page.textContent('#copyNote'),/已复制|已选中/);
   unreachable=true;await page.evaluate(()=>refresh());assert.equal(await page.inputValue('#entry'),entry);assert.match(await page.textContent('#error'),/保存的设备入口/);assert.match(await page.textContent('#connection'),/上次确认/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);assert.ok(calls.every(c=>!c.p.includes('tool')),'onboarding never fetches hardware/configuration tools');
   unreachable=false;await page.evaluate(()=>refresh());await page.locator('#entry').evaluate(e=>{e.blur();e.scrollLeft=0;});
   await page.screenshot({path:path.join(root,'build/firmware-network/setup-'+colorScheme+'.png'),fullPage:true});await page.close();
  }
  // Verify identity before the browser presents a saved pairing credential.
  for(const mismatch of [true,false]){
   const page=await browser.newPage();const sent=[];
   await page.route('http://192.168.1.51/**',async route=>{
    const p=new URL(route.request().url()).pathname;
    if(p==='/wifi-feedback.js')return route.fulfill({contentType:'application/javascript',body:source('wifi_feedback')});
    if(p==='/setup')return route.fulfill({contentType:'text/html',body:source('setup_page')});
    sent.push({p,token:route.request().headers()['x-setup-token']});
    if(p==='/api/identity')return route.fulfill({json:{device_id:mismatch?'other-device':'saved-device'}});
    return route.fulfill({status:401,json:{error:'unauthorized'}});
   });
   await page.goto('http://192.168.1.51/setup#setup_token=saved-credential&device_id=saved-device');
   await page.waitForFunction(()=>document.getElementById('error').textContent.length>0);
   assert.match(await page.textContent('#error'),mismatch?/身份/:/访问权限/);
   assert.equal(sent[0].token||'','');if(mismatch)assert.equal(sent.length,1);
   assert.equal(await page.locator('#join').isDisabled(),true);await page.close();
  }
  console.log('PASS setup page: mobile light/dark, scan/save/progress, stable paired entry, identity mismatch, auth failure and switching-network retention.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
