const fs=require('fs'),path=require('path');const {chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const root=path.resolve(__dirname,'..'),private=JSON.parse(fs.readFileSync(path.join(root,'build/device-lab/device-private.json'),'utf8'));
 try{
  const local=await browser.newPage({viewport:{width:1100,height:1000}});
  await local.goto('http://127.0.0.1:8768/companion');await local.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length===8);
  const status=await local.evaluate(()=>tool('doll_get_status'));
  for(const [label,page,url] of [
   ['computer',local,null],
   ['device',await browser.newPage({viewport:{width:1100,height:1000},httpCredentials:{username:'admin',password:private.ap_password}}),'http://'+status.ip+'/']
  ]){
   const errors=[];page.on('pageerror',e=>errors.push(e.message));if(url)await page.goto(url);
   await page.waitForFunction(()=>document.querySelectorAll('#parts input[name=channel_name]').length===8);
   const original=await page.evaluate(()=>tool('get_channel_config'));
   try{
    await page.click('#addChannel');await page.selectOption('#type8','temperature');await page.fill('#part8','页面温度测试');
    await page.click('#addChannel');await page.selectOption('#type9','vibration');await page.fill('#part9','页面震动测试');
    await page.click('#saveParts');await page.waitForFunction(()=>!document.querySelector('#saveParts').disabled);
    const config=await page.evaluate(()=>tool('get_channel_config'));
    if(config.channels.length!==10||config.channels[8].type!=='temperature'||config.channels[9].type!=='vibration')throw Error('Mixed UI configuration failed');
    await page.selectOption('#channel','8');await page.fill('#pressure','36.5');await page.click('#press');await page.waitForFunction(()=>!document.querySelector('#press').disabled);
    let values=await page.evaluate(()=>tool('read_channel_values'));
    if(values.values.find(v=>v.channel===8).value!==36.5)throw Error('Temperature UI input failed');
    await page.selectOption('#vibrationChannel','9');await page.fill('#duration','200');await page.click('#vibrate');await page.waitForFunction(()=>!document.querySelector('#vibrate').disabled);
    await page.waitForTimeout(500);values=await page.evaluate(()=>tool('read_channel_values'));
    const motor=values.values.find(v=>v.channel===9);if(motor.active||motor.value!==0||motor.source!=='simulation')throw Error('Vibration UI auto-stop/source failed');
    if((await page.textContent('#error')).trim())throw Error(await page.textContent('#error'));
    if(errors.length)throw Error(errors.join('\n'));
    await page.setViewportSize({width:390,height:900});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
    if(overflow)throw Error(label+' mobile layout overflows');
    await page.screenshot({path:path.join(root,'build/device-lab/channels-'+label+'-mobile.png'),fullPage:true});
    console.log(label+': add/edit/save typed channels, temperature input, simulated vibration/auto-stop, mobile layout PASS');
   }finally{await page.evaluate(channels=>tool('set_channel_config',{channels}),original.channels)}
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
