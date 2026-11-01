// Exercise real onboarding and shared controller against delayed/failing local APIs.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('playwright');
const {source}=require('./firmware_test_assets.cjs');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{for(const colorScheme of ['light','dark']){
  const page=await browser.newPage({viewport:{width:390,height:844},colorScheme}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  let scanMode='pending',polls=0,posts=0,saveMode='ok',online=false,associated=false,ip='0.0.0.0',ssid='home',offline=false;
  await page.route('http://192.168.4.1/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/setup')return route.fulfill({contentType:'text/html',body:source('setup_page')});
   if(p==='/wifi-feedback.js')return route.fulfill({contentType:'application/javascript',body:source('wifi_feedback')});
   if(offline)return route.abort('failed');
   if(p==='/api/identity')return route.fulfill({json:{device_id:'test-device'}});
   if(p==='/api/setup')return route.fulfill({json:{token:'fixture',enabled:true}});
   if(p==='/api/status')return route.fulfill({json:{device_id:'test-device',hostname:'ai-doll-001122334455.local',wifi_connected:online,wifi_associated:associated,ip,ssid}});
   if(p==='/api/scan')return route.fulfill({json:scanMode==='error'?{error:'扫描失败，请重试'}:scanMode==='pending'?{scanning:true}:{scanning:false,networks:scanMode==='empty'?[]:[{ssid:'home',secure:true,rssi:-50}]}});
   if(p==='/api/wifi'){posts++;if(saveMode==='error')return route.fulfill({status:500,json:{error:'write result unknown'}});return route.fulfill({json:{ok:true}});}
   throw Error(p);
  });
  await page.goto('http://192.168.4.1/setup');await page.waitForFunction(()=>!document.getElementById('scan').disabled);
  await page.click('#scan');await page.waitForFunction(()=>document.getElementById('scan').getAttribute('aria-busy')==='true');
  assert.match(await page.textContent('#scanHint'),/正在查找/);assert.equal(await page.locator('#join').isDisabled(),true);
  await page.evaluate(()=>refresh());assert.match(await page.textContent('#scanHint'),/正在查找/);
  scanMode='empty';await page.waitForFunction(()=>document.getElementById('scanHint').textContent.includes('没有找到'));
  assert.equal(await page.locator('#scan').isDisabled(),false);await page.evaluate(()=>refresh());assert.match(await page.textContent('#scanHint'),/没有找到/);
  scanMode='error';await page.click('#scan');await page.waitForFunction(()=>document.getElementById('scanHint').dataset.tone==='error');
  scanMode='found';await page.click('#scan');await page.waitForFunction(()=>document.getElementById('networks').options.length===2);await page.selectOption('#networks','home');
  await page.fill('#password','short');await page.click('#join');await page.evaluate(()=>refresh());assert.match(await page.textContent('#joinResult'),/至少8/);assert.equal(posts,0);
  await page.fill('#password','password123');await page.click('#join');await page.waitForFunction(()=>document.getElementById('join').textContent.includes('正在连接'));
  assert.equal(posts,1);assert.equal(await page.locator('#join').isDisabled(),true);assert.equal(await page.locator('#scan').isDisabled(),true);
  online=true;ssid='old-network';ip='192.168.1.99';await page.evaluate(()=>refresh());assert.equal(await page.locator('#openDevice').isVisible(),false);assert.notEqual(await page.getAttribute('#joinResult','data-tone'),'success');
  online=false;associated=true;ssid='home';ip='0.0.0.0';await page.evaluate(()=>refresh());assert.match(await page.textContent('#joinResult'),/获取家庭IP/);
  await page.evaluate(()=>{const original=Date.now;Date.now=()=>original()+31000;});await page.evaluate(()=>refresh());
  assert.match(await page.textContent('#joinResult'),/等待较久/);assert.equal(await page.locator('#join').isDisabled(),false);assert.equal(await page.locator('#checkWifi').isVisible(),true);assert.equal(posts,1);
  await page.click('#checkWifi');assert.equal(posts,1,'Checking must never resend a Wi-Fi password');
  await page.screenshot({path:path.join(__dirname,'../build/wifi-feedback/waiting-'+colorScheme+'.png'),fullPage:true});
  online=true;associated=true;ip='192.168.1.50';await page.evaluate(()=>refresh());assert.equal(await page.getAttribute('#joinResult','data-tone'),'success');assert.equal(await page.locator('#openDevice').isVisible(),true);
  offline=true;await page.evaluate(()=>refresh());await page.waitForTimeout(1100);assert.notEqual(await page.getAttribute('#joinResult','data-tone'),'success');assert.match(await page.textContent('#joinResult'),/不能据此确认/);
  offline=false;online=false;associated=false;ip='0.0.0.0';saveMode='error';await page.evaluate(()=>refresh());await page.fill('#password','password123');await page.click('#join');
  await page.waitForFunction(()=>document.getElementById('joinResult').textContent.includes('保存结果尚未确认'));assert.equal(posts,2);assert.equal(await page.locator('#checkWifi').isVisible(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  for(const id of ['scan','join','copyEntry'])assert.ok((await page.locator('#'+id).boundingBox()).height>=48);
  assert.deepEqual(errors,[]);await page.close();console.log('PASS '+colorScheme+': scan/empty/retry, stable hints, validation, target identity, DHCP wait, slow connection, read-only checks, offline and uncertain save.');
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
