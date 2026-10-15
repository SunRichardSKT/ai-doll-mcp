// Exercise the actual management HTML/JS with explicitly simulated API results.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
  const browser=await chromium.launch({headless:true,executablePath:executable});
  const page=await browser.newPage({viewport:{width:1360,height:960}}),errors=[],actions=[];
  page.on('pageerror',e=>errors.push(e.message));
  const state={environment_ready:true,project:'fixture',version:'2.20.0',paired:false,connection:{},
    collector:{running:false},secure_config:{profile:'interaction',configured:false},secure:{},
    profile_counts:{status:2,history:9,interaction:19},job:{state:'idle'},
    operit:{configured:false,running:false,addresses:['192.168.1.20']}};
  await page.route('http://127.0.0.1:8769/**',async route=>{
    const request=route.request(),p=new URL(request.url()).pathname;
    let body,type='application/json';
    if(p==='/'){body=fs.readFileSync(path.resolve(__dirname,'control_panel.html'),'utf8').replace('__CSRF__','fixture');type='text/html';}
    else if(p==='/control-panel.js'){body=fs.readFileSync(path.resolve(__dirname,'control_panel.js'),'utf8');type='application/javascript';}
    else if(p==='/api/state')body=JSON.stringify(state);
    else if(p==='/api/action'){
      const {action,data}=request.postDataJSON();actions.push({action,data});
      let result={};
      if(action==='operit-save'){state.operit={...state.operit,configured:true,host:data.host,mode:data.mode};result.saved=true;}
      if(action==='operit-start'){state.operit.running=true;result={running:true,protocol_connected:true,tool_count:19};}
      if(action==='operit-stop'){state.operit.running=false;result.stopped=true;}
      state.job={state:'done',action,message:'操作完成',result};body=JSON.stringify({accepted:true});
    } else if(p==='/api/operit-connection')body=JSON.stringify({schema:1,kind:'ai-doll-operit-connection',mcp_url:'http://192.168.1.20:8775/fixture/mcp'});
    else if(p==='/api/operit-toolpkg'){body=Buffer.from('ZIP fixture only');type='application/octet-stream';}
    else body='{}';
    await route.fulfill({status:200,contentType:type,body});
  });
  try {
    await page.goto('http://127.0.0.1:8769/#operit');await page.locator('#operitMode').waitFor({state:'visible'});
    await page.selectOption('#operitMode','simulation');await page.click('#operitStart');
    await page.waitForFunction(()=>document.getElementById('globalNotice').textContent==='操作完成。');
    assert.deepEqual(actions.slice(0,2).map(x=>x.action),['operit-save','operit-start']);
    assert.equal(actions[0].data.host,'192.168.1.20','single network selected without typing');
    const connection=page.waitForEvent('download');await page.click('#operitConnection');
    assert.equal((await connection).suggestedFilename(),'AI_Doll_Connection.json');
    const pkg=page.waitForEvent('download');await page.click('#operitToolpkg');assert.equal((await pkg).suggestedFilename(),'AI_Doll_Operit.toolpkg');
    const output=path.resolve(__dirname,'../build/operit-unified-ui');fs.mkdirSync(output,{recursive:true});
    for(const width of [1360,390]) {
      await page.setViewportSize({width,height:960});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'responsive without overflow');
      await page.screenshot({path:path.join(output,'operit-'+width+'.png'),fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS actual Operit manager UI: navigation, mode choice, automatic network, saved startup and both downloads, desktop/mobile. API fixture, not device/Android proof.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
