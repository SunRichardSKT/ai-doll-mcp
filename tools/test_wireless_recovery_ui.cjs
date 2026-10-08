const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const root=path.resolve(__dirname,'..'),page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('Wi-Fi'));
  await page.click('#discover');
  await page.waitForFunction(()=>document.querySelector('#discoveryHint').textContent.includes('已验证'),{},{timeout:12000});
  const verified=await page.textContent('#discoveryHint');
  if(!verified.includes('AI-Doll-')||!verified.includes('当前地址有效'))throw Error('Read-back discovery result incomplete');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('已连接'));
  await page.waitForFunction(()=>!document.querySelector('#discover').disabled);
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('390px overflow');
  if(errors.length)throw Error(errors.join('\n'));
  await page.screenshot({path:path.join(root,'build/device-lab/wireless-recovery-mobile.png'),fullPage:true,mask:[page.locator('#login')]});
  console.log('PASS: authenticated device discovery button, verified result, healthy Wi-Fi status and 390px layout');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
