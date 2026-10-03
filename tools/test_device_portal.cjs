const fs=require('fs'),path=require('path');const {chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const url=process.env.DOLL_DEVICE_URL||'http://192.168.4.1/';
 const options={viewport:{width:1000,height:1100}};
 if(process.env.DOLL_DEVICE_URL){
  const cfg=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../build/device-lab/device-private.json'),'utf8'));
  options.httpCredentials={username:'admin',password:cfg.ap_password};
 }
 const page=await browser.newPage(options),errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(url);await page.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length===8);
  const original=await page.evaluate(()=>tool('get_body_map'));
  try{
   await page.fill('#part6','页面测试部位');await page.click('#saveParts');await page.waitForFunction(()=>document.querySelector('#partResult').textContent.includes('已保存'));
   await page.selectOption('#channel','6');await page.click('#press');await page.waitForFunction(()=>document.querySelector('#logs').textContent.includes('页面测试部位'));
   await page.uncheck('#enabled');await page.click('#saveMcp');await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('开关已保存'));
   const parts=await page.evaluate(()=>tool('get_body_map'));if(parts.parts[6].name!=='页面测试部位')throw Error('Admin settings unavailable with MCP disabled');
   await page.check('#enabled');await page.click('#saveMcp');await page.waitForFunction(()=>!document.querySelector('#saveMcp').disabled);
   await page.click('#scan');await page.waitForFunction(()=>document.querySelector('#scanHint').textContent.startsWith('找到'),{timeout:45000});
   if(!await page.locator('#networks option').filter({hasText:'Richard'}).count())throw Error('Richard not found');
   if(errors.length)throw Error(errors.join('\n'));
   await page.screenshot({path:path.resolve(__dirname,'../build/device-lab/device-portal.png'),fullPage:true});
  }finally{await page.evaluate(parts=>tool('set_body_map',parts),original);await page.evaluate(()=>api('/api/mcp',{enabled:true}))}
  console.log('Device settings UI: map save, simulation log, MCP switch, Wi-Fi scan: PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
