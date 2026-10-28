// Browser/QR fixtures only. This does not exercise Android or a real device.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const {source}=require('./firmware_test_assets.cjs');
(async()=>{
  const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p=>fs.existsSync(p));
  const browser=await chromium.launch({headless:true,executablePath:executable});
  try{
    const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.setContent('<!doctype html><meta charset="utf-8"><style>body{font:16px system-ui;margin:20px}button{display:block;width:100%;margin:12px 0;padding:12px}textarea{max-width:100%}</style><h1>连接手机 Operit</h1><div id="pairing"></div>');
    await page.addScriptTag({content:source('pairing')});
    await page.addScriptTag({path:path.join(root,'clients/operit/vendor/jsQR.js')});
    const connection={schema:1,kind:'ai-doll-device-connection',mode:'phone',mcp_url:'http://192.168.1.23/mcp',
      device_id:'fixture-device',hostname:'ai-doll-000000000001.local',token:'fixture_token_225_1234',label:'头顶娃娃'};
    await page.evaluate(c=>AIDollPairing.render(document.getElementById('pairing'),c),connection);
    await page.getByRole('button',{name:'显示临时二维码',exact:true}).click();
    const decoded=await page.evaluate(async()=>{
      const image=document.querySelector('img');await image.decode();
      const canvas=document.createElement('canvas');canvas.width=canvas.height=1000;
      const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,1000,1000);ctx.drawImage(image,0,0,1000,1000);
      const result=jsQR(ctx.getImageData(0,0,1000,1000).data,1000,1000);
      if(!result)throw Error('Generated pairing QR could not be decoded');
      const prefix='AIDOLL1:',b64=result.data.slice(prefix.length).replace(/-/g,'+').replace(/_/g,'/');
      return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64),c=>c.charCodeAt(0))));
    });
    assert.deepEqual(decoded,connection);
    await page.getByRole('button',{name:'复制连接码',exact:true}).click();
    assert.ok((await page.locator('textarea').inputValue()).startsWith('AIDOLL1:'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'下载手机连接文件',exact:true}).click();
    const download=await downloadPromise;assert.equal(download.suggestedFilename(),'AI_Doll_Operit_Connection.json');
    const stream=await download.createReadStream(),chunks=[];for await(const chunk of stream)chunks.push(chunk);
    assert.deepEqual(JSON.parse(Buffer.concat(chunks).toString('utf8')),connection);
    const output=path.join(root,'build/pairing-portal');fs.mkdirSync(output,{recursive:true});
    await page.screenshot({path:path.join(output,'pairing-portal-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS: local browser QR round trip, UTF-8 connection code, JSON download and 390px layout');
  }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exitCode=1});
