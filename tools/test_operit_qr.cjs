// Node only by default; --browser also checks a real PNG in Chromium.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),qr=require('../clients/operit/core/qr.js');
const assets={decoder:fs.readFileSync(path.join(root,'clients/operit/vendor/jsQR.js'),'utf8'),
 generator:fs.readFileSync(path.join(root,'clients/operit/vendor/qrcodegen.js'),'utf8')};
const code='AIDOLL1:'+Buffer.from(JSON.stringify({schema:1,kind:'ai-doll-device-connection',mode:'phone',
 label:'同手机二维码 🐱',device_id:'fixture',mcp_url:'http://192.168.1.25/mcp',token:'fixture_token_123456'})).toString('base64url');
const pngHeader=Buffer.from([137,80,78,71,13,10,26,10]).toString('base64');
function pixels(text){
 const generator=vm.runInNewContext(assets.generator+';qrcodegen');
 const symbol=generator.QrCode.encodeText(text,generator.QrCode.Ecc.MEDIUM),scale=5,border=4,size=(symbol.size+border*2)*scale;
 const data=new Uint8ClampedArray(size*size*4);data.fill(255);
 for(let y=0;y<symbol.size;y++)for(let x=0;x<symbol.size;x++)if(symbol.getModule(x,y))
  for(let dy=0;dy<scale;dy++)for(let dx=0;dx<scale;dx++){
   const i=(((y+border)*scale+dy)*size+(x+border)*scale+dx)*4;data[i]=data[i+1]=data[i+2]=0;
  }
 return {data,width:size,height:size};
}
function bridge(image){
 const status={textContent:''},canvas={getContext:()=>({drawImage:()=>{},getImageData:()=>image})};
 const context={window:{},document:{getElementById:id=>id==='status'?status:canvas},Uint8ClampedArray,
  Image:class{constructor(){this.width=image.width;this.height=image.height;}set src(value){setTimeout(()=>this.onload(),5);}}};
 vm.createContext(context);
 const html=qr.html(assets),source=html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>'));
 vm.runInContext(source,context);
 let probes=0;
 return {key:'node-image-double',evaluateJavascript:async script=>{
  if(script.includes('state()'))probes++;
  return {success:true,data:JSON.stringify(vm.runInContext(script,context))};
 },context,probes:()=>probes};
}
async function nodeChecks(){
 const image=pixels(code),realDecoder=require('../clients/operit/vendor/jsQR.js');
 assert.equal(realDecoder(image.data,image.width,image.height).data,code,'real QR matrix → RGBA → real jsQR keeps UTF-8 payload');
 const controller=bridge(image);
 global.Tools={Files:{readBinary:async()=>({contentBase64:pngHeader})},System:{sleep:ms=>new Promise(resolve=>setTimeout(resolve,Math.min(ms,2)))}};
 assert.equal(await qr.decode(controller,'/fixture/image-double.png'),code);
 assert.ok(controller.probes()>1,'start completion is not confused with asynchronous image decode completion');
 assert.deepEqual(qr.unwrap(JSON.stringify({success:true,data:JSON.stringify({state:'done'})})),{state:'done'});
 global.Tools.Files.readBinary=async()=>({contentBase64:'x'.repeat(6*1024*1024)});
 await assert.rejects(qr.decode(controller,'/fixture/oversized.png'),/4MB/);
 global.Tools.Files.readBinary=async()=>({contentBase64:Buffer.from('invalid image').toString('base64')});
 await assert.rejects(qr.decode(controller,'/fixture/invalid.png'),/PNG/);
 global.Tools.Files.readBinary=async()=>({contentBase64:pngHeader});
 const noQR=bridge({...image,data:new Uint8ClampedArray(image.data.length).fill(255)});
 await assert.rejects(qr.decode(noQR,'/fixture/blank.png'),/没有找到/);
 const waiting={key:'cancel-fixture',evaluateJavascript:async script=>script.includes('state()')?{state:'loading'}:true};
 const result=qr.decode(waiting,'/fixture/cancel.png');setTimeout(()=>qr.cancel(waiting),5);
 await assert.rejects(result,/取消/);
 let resolveRead;
 global.Tools.Files.readBinary=()=>new Promise(resolve=>{resolveRead=resolve;});
 const reading=qr.decode(waiting,'/fixture/cancel-during-read.png');await qr.cancel(waiting);
 resolveRead({contentBase64:pngHeader});await assert.rejects(reading,/取消/,'late binary read cannot restart a cancelled request');
 delete global.Tools;
 console.log('PASS: pinned QR matrix/RGBA/jsQR UTF-8 round trip, async image bridge double, invalid/blank/oversized images and cancellation (Node only)');
}
async function browserChecks(){
 const {chromium}=require('playwright');
 const executable=[chromium.executablePath(),'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Google/Chrome/Application/chrome.exe'].find(file=>fs.existsSync(file));
 const browser=await chromium.launch({headless:true,executablePath:executable});
 try{
  const page=await browser.newPage(),requests=[],errors=[];page.on('request',request=>requests.push(request.url()));page.on('pageerror',error=>errors.push(error.message));
  await page.setContent(qr.html(assets));
  const png=await page.evaluate(text=>{
   const symbol=qrcodegen.QrCode.encodeText(text,qrcodegen.QrCode.Ecc.MEDIUM),scale=6,border=4,
    canvas=document.createElement('canvas');canvas.width=canvas.height=(symbol.size+border*2)*scale;
   const context=canvas.getContext('2d');context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.fillStyle='black';
   for(let y=0;y<symbol.size;y++)for(let x=0;x<symbol.size;x++)if(symbol.getModule(x,y))context.fillRect((x+border)*scale,(y+border)*scale,scale,scale);
   return canvas.toDataURL('image/png').split(',')[1];
  },code);
  global.Tools={Files:{readBinary:async()=>({contentBase64:png})},System:{sleep:ms=>new Promise(resolve=>setTimeout(resolve,ms))}};
  const controller={key:'real-browser-fixture',evaluateJavascript:script=>page.evaluate(script)};
  assert.equal(await qr.decode(controller,'/fixture/photo.png'),code,'asynchronous image loading completes before the parsed connection is returned');
  assert.equal(requests.some(url=>/^https?:/.test(url)),false,'all QR generation and decoding stays offline');
  assert.deepEqual(errors,[]);
  assert.deepEqual(qr.unwrap(JSON.stringify({success:true,data:JSON.stringify({state:'done'})})),{state:'done'});
  global.Tools.Files.readBinary=async()=>({contentBase64:'x'.repeat(6*1024*1024)});
  await assert.rejects(qr.decode(controller,'/fixture/oversized.png'),/4MB/);
  global.Tools.Files.readBinary=async()=>({contentBase64:png});
  const waiting={key:'cancel-fixture',evaluateJavascript:async script=>script.includes('state()')?{state:'loading'}:true};
  const result=qr.decode(waiting,'/fixture/cancel.png');setTimeout(()=>qr.cancel(waiting),20);
  await assert.rejects(result,/取消/);
  console.log('PASS: real browser PNG round trip, no network requests, async WebView and cancellation (Android/model remain unverified)');
 }finally{delete global.Tools;await browser.close();}
}
(async()=>{await nodeChecks();if(process.argv.includes('--browser'))await browserChecks();})().catch(error=>{delete global.Tools;console.error(error.stack||error);process.exitCode=1});
