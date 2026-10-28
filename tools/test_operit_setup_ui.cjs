// Exercise the actual management HTML/JS with explicitly simulated API results.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
  const browser=await chromium.launch({headless:true,executablePath:executable});
  const page=await browser.newPage({viewport:{width:1360,height:960}}),errors=[],actions=[];
  page.on('pageerror',e=>errors.push(e.message));
  const state={environment_ready:true,project:'fixture',version:'0.1.0',paired:false,connection:{},
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
    assert.equal(await page.inputValue('#operitMode'),'device','physical device is the ordinary default');
    await page.check('#operitDeveloper');await page.selectOption('#operitMode','simulation');await page.click('#operitStart');
    await page.waitForFunction(()=>document.getElementById('globalNotice').textContent.startsWith('操作完成'));
    assert.deepEqual(actions.slice(0,2).map(x=>x.action),['operit-save','operit-start']);
    assert.equal(actions[0].data.host,'192.168.1.20','single network selected without typing');
    const connection=page.waitForEvent('download');await page.click('#operitConnection');
    assert.equal((await connection).suggestedFilename(),'AI_Doll_Connection.json');
    const pkg=page.waitForEvent('download');await page.click('#operitToolpkg');assert.equal((await pkg).suggestedFilename(),'AI_Doll_Operit.toolpkg');
    state.collector={running:true,device_ip:'192.168.1.50',last_sync:Date.now()/1000};
    state.connection.device_host='192.168.1.99';
    await page.click('[data-view="device"]');
    await page.waitForFunction(()=>document.getElementById('deviceAddress').textContent.includes('192.168.1.50'));
    assert.equal(await page.getAttribute('#openDevice','href'),'http://192.168.1.50/','settings uses confirmed device IP rather than saved host');
    state.collector={running:true,device_ip:null,collector_error:'offline'};
    await page.waitForFunction(()=>document.getElementById('deviceAddress').textContent.includes('尚未确认'));
    assert.equal(await page.getAttribute('#openDevice','href'),'http://192.168.4.1/');
    state.operit.addresses=['192.168.1.21'];
    await page.click('[data-view="operit"]');
    await page.waitForFunction(()=>document.getElementById('operitStatus').textContent.includes('已不在当前网络'));
    assert.equal(await page.inputValue('#operitHost'),'192.168.1.21','new available PC IP is selectable');
    state.collector={running:false};
    await page.click('[data-view="simulation"]');
    assert.equal(await page.locator('#developerPanel').getAttribute('open'),null,'developer iframe remains opt-in');
    assert.equal(await page.locator('iframe').count(),0,'closed developer panel mounts no hidden iframe');
    state.secure_config={configured:true,profile:'interaction',tunnel_id:'tunnel_fixture'};
    state.secure={checked_at:Date.now()/1000,connection_message:'上游服务暂时限流',runtime_running:true,tunnel_connected:false};
    await page.click('[data-view="mcp"]');
    await page.click('#view-mcp [data-action="repair-connection"]');
    await page.waitForFunction(()=>document.getElementById('globalNotice').textContent.startsWith('操作完成'));
    assert.equal(actions.at(-1).action,'repair-connection');
    assert.ok((await page.textContent('#tunnelDetail')).includes('上游服务暂时限流'),'show concrete tunnel connection reason');
    await page.click('[data-view="operit"]');
    const output=path.resolve(__dirname,'../build/operit-unified-ui');fs.mkdirSync(output,{recursive:true});
    for(const width of [1360,390]) {
      await page.setViewportSize({width,height:960});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'responsive without overflow');
      await page.screenshot({path:path.join(output,'operit-'+width+'.png'),fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS actual Operit manager UI: navigation, mode choice, automatic network, saved startup and both downloads, desktop/mobile. API fixture, not device/Android proof.');
  } catch(error) {console.error('UI state:',await page.textContent('#globalNotice'),'actions:',actions);throw error;}
  finally {if(errors.length)console.error('Browser errors:',errors);await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
