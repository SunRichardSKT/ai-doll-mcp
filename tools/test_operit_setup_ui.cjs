// Exercise the actual management HTML/JS with explicitly simulated API results.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
  const browser=await chromium.launch({headless:true,executablePath:executable});
  const page=await browser.newPage({viewport:{width:1360,height:960}}),errors=[],actions=[];
  page.on('pageerror',e=>errors.push(e.message));
  const state={environment_ready:true,project:'fixture',version:'0.1.1',paired:false,connection:{},
    collector:{running:false},secure_config:{profile:'interaction',configured:false},secure:{},
    profile_counts:{status:2,history:9,interaction:19},job:{state:'idle'},
    serial_ports:[{port:'COM8',label:'USB 开发板'}],operit:{configured:false,running:false,addresses:['192.168.1.20']}};
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
      if(action==='client-config'||action==='claude-config'){
        const config={mcpServers:{ai_doll:{command:'C:/runtime/python.exe',args:['C:/project/tools/companion_mcp.py']}}};
        if(data.client==='claude_code')config.mcpServers.ai_doll.type='stdio';
        result=action==='claude-config'?{saved:true,config}:config;
      }
      if(action==='usb'){state.connection={transport:'usb',serial_port:data.port};state.collector={running:true,transport:'usb',device_ip:'192.168.1.50'};}
      if(action==='usb-pair-wifi'){state.paired=true;state.connection={transport:'wifi',device_host:'192.168.1.50'};state.collector={running:true,transport:'wifi',device_ip:'192.168.1.50'};}
      state.job={state:'done',action,message:'操作完成',result};body=JSON.stringify({accepted:true});
    } else if(p==='/api/operit-connection')body=JSON.stringify({schema:1,kind:'ai-doll-operit-connection',mcp_url:'http://192.168.1.20:8775/fixture/mcp'});
    else if(p==='/api/operit-toolpkg'){body=Buffer.from('ZIP fixture only');type='application/octet-stream';}
    else body='{}';
    await route.fulfill({status:200,contentType:type,body});
  });
  try {
    await page.goto('http://127.0.0.1:8769/#operit');await page.locator('#operitMode').waitFor({state:'visible'});
    await page.click('[data-view="setup"]');await page.click('[data-step="1"]');
    assert.equal(await page.inputValue('#serialPort'),'COM8','single detected board is selected');
    assert.equal(await page.locator('#deviceHost').isVisible(),false,'manual credentials start folded');
    await page.click('#connectUsb');await page.waitForFunction(()=>document.getElementById('globalNotice').textContent==='操作完成');
    await page.waitForFunction(()=>document.getElementById('usbProgress').textContent.includes('192.168.1.50'));
    assert.deepEqual(actions.slice(0,2).map(x=>x.action),['usb','usb-pair-wifi'],'already networked USB board pairs without a Wi-Fi form');
    assert.equal(await page.locator('iframe').count(),0);
    await page.click('[data-step="2"]');assert.equal(await page.inputValue('#hostChoice'),'','new users choose their app explicitly');
    await page.selectOption('#hostChoice','operit');
    assert.equal(await page.locator('#operitStart').isVisible(),true,'Operit startup is available directly in the wizard');
    await page.click('[data-step="3"]');assert.equal(await page.locator('#verifyOperit').isVisible(),true);
    assert.equal(await page.locator('#verificationPrompt').isVisible(),false,'Operit never requires ChatGPT call IDs');
    await page.click('[data-step="2"]');await page.selectOption('#hostChoice','secure');
    await page.click('[data-step="3"]');assert.equal(await page.locator('#connectionId').isVisible(),true);
    await page.click('[data-step="2"]');await page.selectOption('#hostChoice','local');
    assert.equal(await page.locator('#localConfig').isVisible(),true);
    await page.selectOption('#hostChoice','claude');await page.click('#installClaude');
    await page.waitForFunction(()=>document.getElementById('localConfig').textContent.includes('mcpServers'));
    assert.equal(actions.at(-1).action,'claude-config');
    const localDownload=page.waitForEvent('download');await page.click('#downloadLocalConfig');
    assert.equal((await localDownload).suggestedFilename(),'AI_Doll_Local_MCP.json');
    await page.selectOption('#hostChoice','claude_code');
    assert.equal(await page.locator('#claudeCodeActions').isVisible(),true);
    assert.equal(await page.locator('#installClaude').isVisible(),false);
    assert.match(await page.textContent('#claudeCodeActions'),/claude --mcp-config/);
    const codeDownload=page.waitForEvent('download');await page.click('#downloadLocalConfig');
    assert.equal((await codeDownload).suggestedFilename(),'AI_Doll_Claude_Code.json');
    assert.equal(actions.at(-1).data.client,'claude_code');
    assert.equal(JSON.parse(await page.textContent('#localConfig')).mcpServers.ai_doll.type,'stdio');
    assert.equal(actions.filter(x=>x.action==='claude-config').length,1,'Code export never invokes Desktop config writer');
    await page.click('[data-step="3"]');assert.match(await page.textContent('#mcpVerifyHint'),/Claude Code/);
    await page.click('[data-step="2"]');
    await page.selectOption('#hostChoice','claude_http');
    assert.equal(await page.locator('#setupCloud').isVisible(),true);
    await page.fill('#cloudMcpURL','https://192.168.1.50/private/mcp');await page.click('#copyCloudMcp');
    assert.match(await page.textContent('#globalNotice'),/公网 HTTPS/);
    await page.fill('#cloudMcpURL','https://fixture.example:8443/private/mcp');await page.click('#copyCloudMcp');
    assert.match(await page.textContent('#globalNotice'),/443/);
    await page.selectOption('#hostChoice','chatgpt_http');
    assert.match(await page.textContent('#cloudInstructions'),/Server URL/);
    await page.selectOption('#hostChoice','gemini_http');
    assert.match(await page.textContent('#cloudInstructions'),/Connected Apps/);
    assert.match(await page.textContent('#cloudNetworkHint'),/Keep Activity/);
    assert.equal(await page.locator('#setupCloud').isVisible(),true);
    await page.selectOption('#hostChoice','deepseek');
    assert.equal(await page.locator('#setupDeepSeek').isVisible(),true);
    assert.equal(await page.locator('#setupLocal').isVisible(),true);
    assert.match(await page.textContent('#localClientHint'),/cordis.patch.yml/);
    await page.click('#setupLocal [data-action="client-config"]');
    await page.waitForFunction(()=>document.getElementById('globalNotice').textContent.startsWith('操作完成'));
    assert.equal(actions.at(-1).data.client,'deepseek');
    await page.click('[data-step="3"]');
    assert.equal(await page.locator('#verificationPrompt').isVisible(),true);
    await page.click('[data-step="2"]');await page.selectOption('#hostChoice','gemini');
    assert.match(await page.textContent('#localClientHint'),/\.gemini\/settings.json/);
    await page.click('#setupLocal [data-action="client-config"]');
    await page.waitForFunction(()=>document.getElementById('globalNotice').textContent.startsWith('操作完成'));
    assert.equal(actions.at(-1).data.client,'gemini');
    await page.click('[data-step="2"]');
    await page.selectOption('#hostChoice','operit');await page.click('[data-view="operit"]');actions.length=0;
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
    console.log('PASS manager UI: ChatGPT tunnel/HTTPS, Claude local/HTTPS, DeepSeek guidance, Operit, local MCP, USB pairing, downloads and responsive layout. API fixtures.');
  } catch(error) {console.error('UI state:',await page.textContent('#globalNotice'),'actions:',actions);throw error;}
  finally {if(errors.length)console.error('Browser errors:',errors);await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
