const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),work=path.join(root,'build/device-lab');
 const proof=JSON.parse(fs.readFileSync(path.join(work,'offline-device-test.json'),'utf8'));
 if(!proof.passed)throw Error('Complete offline hardware test first');
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable}),errors=[];
 try{
  const page=await browser.newPage({viewport:{width:390,height:900}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/companion/tool',async route=>{
   const body=route.request().postDataJSON();
   // Read the real archived unknown-time test rows rather than synthetic UI data.
   if(body.name==='query_device_history'&&!body.arguments.date&&body.arguments.after===0){
    body.arguments.after=proof.unknown_archive_cursor;body.arguments.limit=4;
    return route.continue({postData:JSON.stringify(body)});
   }
   return route.continue();
  });
  await page.goto('http://127.0.0.1:8768/companion');
  await page.waitForFunction(()=>document.querySelector('#storageStatus').textContent.includes('Flash 缓存可用'));
  await page.uncheck('#live');
  await page.click('#checkStorage');
  await page.waitForFunction(()=>document.querySelector('#storageStatus').textContent.includes('待补传 0/256'));
  if((await page.textContent('#history')).includes('时间未知'))throw Error('Undated history leaked into today');
  await page.click('#all');
  await page.waitForFunction(()=>document.querySelectorAll('#history tr').length===4&&document.querySelector('#history').textContent.includes('时间未知'));
  const times=await page.locator('#history tr td:first-child').allTextContents();
  if(times.some(t=>t!=='时间未知'))throw Error('Unknown time was guessed or rendered as 1970');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Companion mobile overflow');
  await page.locator('#storageStatus').locator('..').screenshot({path:path.join(work,'offline-cache-mobile.png')});
  const cfg=JSON.parse(fs.readFileSync(path.join(work,'device-private.json'),'utf8'));
  const connection=JSON.parse(fs.readFileSync(path.join(work,'connection-private.json'),'utf8'));
  const device=await browser.newPage({viewport:{width:390,height:900},httpCredentials:{username:'admin',password:cfg.ap_password}});
  device.on('pageerror',e=>errors.push(e.message));
  await device.goto('http://'+connection.device_host+'/');
  await device.waitForFunction(()=>document.querySelector('#storageStatus')?.textContent.includes('256'));
  if(await device.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Device mobile overflow');
  await device.locator('#storageStatus').screenshot({path:path.join(work,'device-offline-cache-mobile.png')});
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync(path.join(work,'offline-ui-test.json'),JSON.stringify({passed:true,at:new Date().toISOString(),checks:['real flash cache status on companion and device','unknown archive rows display unknown only in all dates','390px mobile layout and no JavaScript errors']},null,2));
  console.log('PASS: actual cache status, four actual unknown-time rows, date isolation and 390px panels');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
