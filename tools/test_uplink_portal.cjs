/* Real phone-sized device page plus an explicit offline-status UI fixture. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('playwright');
const folder=path.resolve(__dirname,'../build/direct-device-test');
const cfg=JSON.parse(fs.readFileSync(process.env.DOLL_UPLINK_DEVICE_CONFIG||path.join(folder,'device-private.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},httpCredentials:{username:'admin',password:cfg.ap_password}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://'+cfg.host+'/');await page.waitForFunction(()=>document.querySelector('#serverURL')?.value.length>0);
  await page.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length===8&&document.querySelector('#state').textContent.includes('已联网'));
  assert(await page.locator('#serverEnabled').isChecked());assert(await page.locator('#serverUseCA').isChecked());
  await page.locator('#checkServer').click();await page.waitForFunction(()=>document.querySelector('#serverStatus').textContent.includes('已直连服务器'));
  await page.screenshot({path:path.join(folder,'device-mobile.png'),fullPage:true});
  await page.route('**/api/uplink',route=>route.request().method()==='GET'?route.fulfill({contentType:'application/json',body:JSON.stringify({enabled:true,server_url:'https://offline.example.com',local_http:false,token_saved:true,custom_ca_saved:false,connected:false,error:'http_transport_fixture'})}):route.continue());
  await page.reload();await page.waitForFunction(()=>document.querySelector('#serverURL').value==='https://offline.example.com');
  assert(await page.locator('#serverEnabled').isChecked());assert(!(await page.locator('#serverUseCA').isChecked()));
  assert((await page.locator('#serverStatus').textContent()).includes('http_transport_fixture'));
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,real_device_page:true,mobile_width:390,online_status:true,offline_status_fixture:true,configuration_not_modified:true}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
