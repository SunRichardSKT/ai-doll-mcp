// Real browser with the production device page; radio and HTTP are explicit doubles.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'..');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p=>fs.existsSync(p));
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{
  const page=await browser.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));
  const html=fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8').split('R"HTML(')[1].split(')HTML"')[0];
  const token='fixture_hotspot_token_225';let windowOpen=false;
  await page.route('http://192.168.1.23/**',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;requests.push({p,token:req.headers()['x-setup-token'],body:req.postData()});
   if(p==='/')return route.fulfill({contentType:'text/html',body:html});
   const asset={'/channel-editor.js':'tools/channel_editor.js','/ota-manager.js':'tools/ota_manager.js'}[p];
   if(asset)return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.join(root,asset),'utf8')});
   if(p==='/pairing.js')return route.fulfill({contentType:'application/javascript',body:'window.AIDollPairing={};'});
   if(req.headers()['x-setup-token']!==token)return route.fulfill({status:401,json:{error:'请从已配对客户端打开设置'}});
   let data={};
   if(p==='/api/setup')data={token,enabled:true,auth_enabled:false};
   if(p==='/api/status')data={wifi_connected:true,ip:'192.168.1.23',hostname:'ai-doll-000000000001.local',config_ap_open:windowOpen,setup_remaining_sec:windowOpen?600:0,setup_window_supported:true,event_storage:{available:true,pending_records:0,max_records:256}};
   if(p==='/api/uplink')data={enabled:false};
   if(p==='/api/tool'){
    const name=JSON.parse(req.postData()).params.name;
    const value=name==='get_channel_config'?{channels:[]}:name==='get_channel_values'?{values:[],channels:[]}:{enabled:true,channels:[]};
    data={result:{content:[{type:'text',text:JSON.stringify(value)}]}};
   }
   if(p==='/api/hotspot'){const v=JSON.parse(req.postData());if(v.action==='open')windowOpen=true;if(v.action==='close')windowOpen=false;data={ok:true};}
   return route.fulfill({json:data});
  });
  await page.goto('http://192.168.1.23/');await page.waitForFunction(()=>document.getElementById('error').textContent.length>0);
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('aidoll_setup_token')),null);
  await page.goto('http://192.168.1.23/#setup_token='+token);await page.reload();
  await page.waitForFunction(()=>document.getElementById('token').textContent.length>0);
  assert.equal(await page.evaluate(()=>location.hash),'');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('aidoll_setup_token')),token);
  await page.waitForFunction(()=>document.getElementById('deviceIP').getAttribute('href')?.includes('#setup_token='));
  assert.equal(await page.locator('#deviceIP').getAttribute('href'),'http://192.168.1.23/#setup_token='+token);
  await page.locator('#openHotspot').click();await page.waitForFunction(()=>document.getElementById('hotspotStatus').textContent.includes('600'));
  await page.locator('#hotspotPassword').fill('123');await page.locator('#saveHotspotPassword').click();
  assert.match(await page.locator('#error').textContent(),/8～63/);
  await page.locator('#hotspotPassword').fill('fixture-pass');await page.locator('#saveHotspotPassword').click();
  await page.waitForFunction(()=>document.getElementById('hotspotPassword').value==='');
  await page.locator('#closeHotspot').click();await page.waitForFunction(()=>document.getElementById('hotspotStatus').textContent.includes('安排关闭'));
  assert.ok(requests.some(r=>r.p==='/api/hotspot'&&JSON.parse(r.body).action==='password'&&r.token===token));
  assert.deepEqual(errors,[]);console.log('PASS: protected LAN bootstrap, fragment/session credential, linked settings, temporary hotspot controls and password validation');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||e);process.exitCode=1});
