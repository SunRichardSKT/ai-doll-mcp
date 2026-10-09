const fs=require('fs'),path=require('path');const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const source=fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8');
 const html=source.split('R"HTML(')[1].split(')HTML";')[0].replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'');
 const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(html);
  await page.evaluate(()=>{
   window.$=id=>document.getElementById(id);window.requests=[];
   window.tool=async(name,args)=>{requests.push({name,args});if(name==='scan_input_devices')return {devices:[{rom:'280102030405069e'},{rom:'2800020304050600'}]};if(name==='set_channel_config')return {channels:args.channels};throw Error('Unexpected fixture tool '+name)};
  });
  await page.addScriptTag({path:path.join(root,'tools/channel_editor.js')});
  await page.evaluate(()=>{
   channelCapabilities={max_channels:16,types:[{type:'pressure',drivers:['simulation','mux_adc','gpio_adc']},{type:'temperature',drivers:['simulation','mux_adc','gpio_adc','ds18b20']},{type:'vibration',drivers:['simulation','gpio_pwm']}]};
   channelDraft=[{channel:0,name:'头部',type:'pressure',driver:'mux_adc',mux_port:0,enabled:true,options:{press_threshold:1200,release_threshold:800}},
    {channel:8,name:'腹部温度',type:'temperature',driver:'simulation',enabled:true,options:{}}];renderChannelEditor();$('channel').onchange=inputTypeChanged;
  });
  await page.selectOption('#driver8','ds18b20');
  if(await page.inputValue('#binding8')!=='1')throw Error('Digital pin default');
  const options=JSON.parse(await page.inputValue('#options8'));if(options.model!=='ds18b20'||options.r0_ohm!==undefined)throw Error('Digital options not separated from NTC');
  await page.getByRole('button',{name:'扫描数字温度探头',exact:true}).last().click();
  const select=page.getByLabel('CH8 扫描到的探头');await select.selectOption('280102030405069e');
  if(await page.inputValue('#rom8')!=='280102030405069e')throw Error('ROM selection');
  await page.evaluate(()=>saveChannelEditor());
  const saved=await page.evaluate(()=>requests.find(r=>r.name==='set_channel_config').args.channels);
  if(saved[1].rom!=='280102030405069e'||saved[1].driver!=='ds18b20'||saved[0].options.press_threshold!==1200)throw Error('ROM round trip or pressure parameters changed');
  await page.selectOption('#channel','8');if(await page.getAttribute('#pressure','min')!=='-55')throw Error('Digital model range');
  await page.selectOption('#driver8','gpio_adc');
  const draft=await page.evaluate(()=>readChannelDraft());if(draft[1].rom!==undefined||draft[1].options.model==='ds18b20')throw Error('Stale ROM/model survives driver change');
  await page.selectOption('#driver8','ds18b20');
  await page.locator('#rom8').scrollIntoViewIfNeeded();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  await page.screenshot({path:path.join(root,'build/device-lab/digital-temperature-fixture-mobile.png')});
  console.log('PASS: isolated digital probe scan/selection/config round trip, driver change and 390px layout');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
