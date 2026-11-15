// Actual desktop settings page; isolated HTTP fixtures, no user service or device touched.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
 const browser=await chromium.launch({headless:true,executablePath:executable});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 let preferences={body_combinations:[]};const root=path.resolve(__dirname,'..');
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://combo.test/**',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.pathname==='/bridge')return route.fulfill({contentType:'text/html',body:fs.readFileSync(path.join(root,'tools/bridge_demo.html'),'utf8')});
  if(url.pathname.endsWith('.js')){const filename={'/bridge-client.js':'bridge_client.js','/body-combinations-ui.js':'body_combinations_ui.js','/console-embed.js':'console_embed.js'}[url.pathname];return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(root,'tools',filename),'utf8')});}
  const d=request.postDataJSON();let data;
  const channels=[0,1].map(channel=>({channel,name:channel?'后背':'前胸',type:'pressure',mode:'connected',enabled:true}));
  if(d.name==='get_device_overview')data={channels,preferences};
  else if(d.name==='get_channel_config')data={channels};
  else if(d.name==='update_companion_preferences'){preferences={...preferences,...d.arguments.changes};data={preferences};}
  else if(d.name==='get_feedback_preferences')data={feedback:{tone:'温柔',preferred_address:'',avoid_phrases:[],max_characters:160},policy:{quiet_hours:{enabled:false,start:'23:00',end:'07:00',timezone:'UTC'}}};
  else throw Error('Unexpected fixture request '+d.name);
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 try{
  await page.goto('https://combo.test/bridge');await page.locator('#comboPorts input').first().waitFor();
  await page.check('#comboPorts input[value="0"]');await page.check('#comboPorts input[value="1"]');
  await page.fill('#comboName','拥抱');await page.click('#saveCombo');
  await page.waitForFunction(()=>document.getElementById('comboList').textContent.includes('拥抱'));
  assert.deepEqual(preferences.body_combinations,[{name:'拥抱',channels:[0,1],window_ms:1500}]);
  await page.reload();await page.getByRole('button',{name:'删除',exact:true}).click();
  await page.waitForFunction(()=>!document.getElementById('comboList').textContent.includes('拥抱'));
  assert.deepEqual(preferences.body_combinations,[]);assert.deepEqual(errors,[]);
  console.log('PASS desktop combinations: actual page create, reload, delete and channel labels. Isolated API fixture.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
