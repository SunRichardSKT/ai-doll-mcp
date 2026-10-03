const fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const page=await browser.newPage({viewport:{width:1100,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:8768/companion');
  await page.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length===8);
  await page.waitForFunction(()=>document.querySelector('#history tr'));
  await page.click('#start');
  await page.waitForFunction(()=>document.querySelector('#mode').textContent==='互动模式');
  await page.selectOption('#channel','4');
  await page.click('#press');
  await page.waitForFunction(()=>document.querySelector('#feedback').textContent.includes('模拟输入已发送'));
  await page.click('#release');
  await page.click('#end');
  await page.waitForFunction(()=>document.querySelector('#mode').textContent.includes('普通模式'));
  await page.click('#query');
  await page.waitForFunction(()=>!document.querySelector('#query').disabled);
  if((await page.textContent('#error')).trim())throw Error(await page.textContent('#error'));
  if(errors.length)throw Error(errors.join('\n'));
  await page.screenshot({path:path.resolve(__dirname,'../build/device-lab/companion-ui.png'),fullPage:true});
  console.log('Browser: mapping loaded, history rendered, start/press/release/end: PASS');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
