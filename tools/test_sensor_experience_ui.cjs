const fs=require('fs'),path=require('path'),{chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable}),root=path.resolve(__dirname,'..');
 try{
  const private=JSON.parse(fs.readFileSync(path.join(root,'build/device-lab/device-private.json'),'utf8'));
  const status=JSON.parse(fs.readFileSync(path.join(root,'build/device-lab/latest-status.json'),'utf8'));
  for(const [label,url] of [['computer','http://127.0.0.1:8768/companion'],['device','http://'+status.ip+'/']]){
  const page=await browser.newPage({viewport:{width:390,height:900},httpCredentials:{username:'admin',password:private.ap_password}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.waitForFunction(()=>document.querySelector('#operatingStatus')?.textContent.includes('手动模式'));
  await page.click('#dailyMode');await page.waitForFunction(()=>!document.querySelector('#dailyMode').disabled);
  if(!(await page.textContent('#error')).includes('请先确认'))throw Error('Missing hardware confirmation accepted');
  await page.click('#calibrateIdle');await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('physical pressure'));
  if(!(await page.textContent('#error')).includes('physical pressure'))throw Error('Bare board calibration not rejected');
  if(!(await page.locator('#applyCalibration').isDisabled()))throw Error('Invalid calibration can be saved');
  await page.selectOption('#channel','0');await page.fill('#pressure','1800');await page.click('#press');
  await page.waitForFunction(()=>document.querySelector('#diagnosticSummary').textContent.includes('1800'));
  if(!(await page.textContent('#diagnosticSummary')).includes('simulation'))throw Error('Source label missing');
  await page.click('#release');await page.waitForFunction(()=>document.querySelector('#diagnosticSummary').textContent.includes('已释放'));
  const image=await page.evaluate(()=>document.querySelector('#diagnosticCanvas').toDataURL());if(image.length<2000)throw Error('Diagnostic canvas not rendered');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile layout overflow');
  if(errors.length)throw Error(errors.join('\n'));
  await page.locator('#sensorExperience').screenshot({path:path.join(root,'build/device-lab/sensor-experience-'+label+'-mobile.png')});
  console.log(label+' PASS: confirmation gate, physical calibration rejection, disabled invalid save, simulation chart and release, mobile layout');
  await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
