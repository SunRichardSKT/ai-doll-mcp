// Actual server page and script; API fixtures are explicit, not a cloud deployment.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const executable=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
  const browser=await chromium.launch({headless:true,executablePath:executable});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const id='ab'.repeat(16);
  await page.route('https://doll.example/**',async route=>{
    const pathname=new URL(route.request().url()).pathname;
    let body,type='application/json',headers={};
    if(pathname==='/'){body=fs.readFileSync(path.join(__dirname,'direct_server.html'));type='text/html';}
    else if(pathname==='/direct-server.js'){body=fs.readFileSync(path.join(__dirname,'direct_server.js'));type='application/javascript';}
    else if(pathname==='/api/server')body=JSON.stringify({server_url:'https://doll.example',local_setup:false});
    else if(pathname==='/api/devices')body=JSON.stringify({devices:[{id,label:'我的娃娃',online:true,
      hardware_id:'AI-Doll-fixture',last_sync:Date.now()/1000,mcp_url:'https://doll.example/example/d/'+id+'/mcp'}]});
    else if(pathname==='/api/operit/toolpkg'){
      body=fs.readFileSync(path.join(__dirname,'../delivery/AI_Doll_Operit.toolpkg'));type='application/zip';
      headers={'Content-Disposition':'attachment; filename="AI_Doll_Operit.toolpkg"'};
    }else if(pathname.endsWith('/operit-connection.json')){
      body=JSON.stringify({schema:1,kind:'ai-doll-operit-connection',mode:'server',mcp_url:'https://doll.example/example/d/'+id+'/mcp'});
      headers={'Content-Disposition':'attachment; filename="AI_Doll_Operit_Connection.json"'};
    }else body='{}';
    await route.fulfill({status:200,contentType:type,headers,body});
  });
  try{
    await page.goto('https://doll.example/');
    await page.getByRole('link',{name:'下载 Operit 连接文件',exact:true}).waitFor();
    const pkg=page.waitForEvent('download');await page.getByRole('link',{name:'下载手机工具包',exact:true}).click();
    assert.equal((await pkg).suggestedFilename(),'AI_Doll_Operit.toolpkg');
    const connection=page.waitForEvent('download');await page.getByRole('link',{name:'下载 Operit 连接文件',exact:true}).click();
    assert.equal((await connection).suggestedFilename(),'AI_Doll_Operit_Connection.json');
    const out=path.join(__dirname,'../build/operit-no-pc-ui');fs.mkdirSync(out,{recursive:true});
    for(const width of [390,1360]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'no horizontal overflow');
      await page.screenshot({path:path.join(out,'server-'+width+'.png'),fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('PASS server Operit setup page: real HTML/JS, both downloads, device identity, mobile and desktop. Explicit API fixture.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
