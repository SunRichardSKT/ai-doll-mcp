const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable}),root=path.resolve(__dirname,'..');
 const page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));let original=null;
 try{
  await page.goto('http://127.0.0.1:8768/bridge');await page.waitForFunction(()=>document.querySelector('#selected').textContent.includes('CH'));
  const active=await page.evaluate(()=>client.tool('get_interaction_status'));if(active.active_session)throw Error('Do not change a user interaction');
  original=await page.evaluate(()=>client.tool('get_feedback_preferences'));
  await page.fill('#address','测试称呼');await page.fill('#avoid','不要说测试词\n<文字不是 HTML>');
  await page.check('#quietEnabled');await page.fill('#quietStart','00:00');await page.fill('#quietEnd','00:00');
  await page.click('#save');await page.waitForFunction(()=>document.querySelector('#savedPreferences').textContent.includes('已保存'));
  await page.reload();await page.waitForFunction(()=>document.querySelector('#selected').textContent.includes('CH'));
  if(await page.inputValue('#address')!=='测试称呼'||!(await page.inputValue('#avoid')).includes('<文字不是 HTML>'))throw Error('Preference persistence/text safety failed');
  if(!(await page.locator('#quietEnabled').isChecked()))throw Error('Quiet switch did not persist');
  await page.click('#checkConnection');await page.waitForFunction(()=>document.querySelector('#checkStatus').textContent.includes('可用工具：35'));
  const check=await page.textContent('#checkStatus');if(!check.includes('设备在线')||!check.includes('Wi-Fi')||!check.includes('暂停主动反馈')||!check.includes('客户端支持'))throw Error('Selfcheck is incomplete');
  await page.fill('#quietZone','Unknown/Zone');await page.click('#save');await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('timezone'));
  const prefs=await page.evaluate(()=>client.tool('get_feedback_preferences'));if(prefs.policy.quiet_hours.timezone!=='Asia/Shanghai')throw Error('Invalid timezone overwrote valid preferences');
  await page.fill('#quietZone','Asia/Shanghai');await page.locator('summary').click();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('390px mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  await page.locator('#feedbackSettings').screenshot({path:path.join(root,'build/device-lab/feedback-preferences-mobile.png')});
  console.log('PASS: preference save/reload, literal phrase data, quiet switch, live device selfcheck, invalid timezone rejection and mobile layout');
 }finally{if(original)await page.evaluate(data=>client.api('/bridge/preferences',data),original);await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
