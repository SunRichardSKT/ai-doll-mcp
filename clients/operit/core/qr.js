// The build embeds audited vendor source in qr_assets.js. No network or file URL.
const active=new Map();
function html(assets){
 const source=assets||require('./qr_assets.js');
 const script=text=>String(text).replace(/<\/script/gi,'<\\/script');
 return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
  '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; img-src data:; style-src \'unsafe-inline\'">'+
  '<style>:root{color-scheme:light dark}body{font:15px sans-serif;margin:12px;background:transparent}canvas{display:none}p{margin:4px}</style></head><body><p id="status">本地二维码读取器已准备。</p><canvas id="image"></canvas><script>'+script(source.decoder)+'\n'+script(source.generator)+'\n'+
  '('+browserRuntime.toString()+')();</script></body></html>';
}
function browserRuntime(){
 let generation=0,result={state:'ready'};
 const status=document.getElementById('status');
 window.aiDollQR={
  state:()=>result,
  cancel:()=>{generation++;result={state:'cancelled'};status.textContent='已取消读取。';return true;},
  start:(data,id)=>{
   const current=++generation;result={state:'loading',id};status.textContent='正在本地读取二维码……';
   if(typeof data!=='string'||data.length>6*1024*1024||!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(data)){
    result={state:'error',id,error:'请选择不超过4MB的PNG、JPEG或WebP图片。'};return false;
   }
   const image=new Image();
   image.onerror=()=>{if(current===generation)result={state:'error',id,error:'图片无法读取，请重新拍照或选择二维码截图。'};};
   image.onload=()=>{
    if(current!==generation)return;
    try{
     if(!image.width||!image.height||image.width*image.height>20000000)throw Error('图片尺寸过大，请裁剪到二维码附近后重试。');
     const scale=Math.min(1,1600/Math.max(image.width,image.height)),canvas=document.getElementById('image');
     canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));
     const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0,canvas.width,canvas.height);
     const pixels=context.getImageData(0,0,canvas.width,canvas.height),code=jsQR(pixels.data,canvas.width,canvas.height,{inversionAttempts:'attemptBoth'});
     if(!code?.data)throw Error('没有找到清晰二维码。请对准完整二维码，或改用连接文件／连接码。');
     if(code.data.length>16384)throw Error('二维码连接内容过长。');
     if(current===generation){result={state:'done',id,text:code.data};status.textContent='二维码已读取，正在核对连接。';}
     canvas.width=canvas.height=1;
    }catch(error){if(current===generation){result={state:'error',id,error:String(error.message||error)};status.textContent=result.error;}}
   };
   image.src=data;return true;
  }
 };
}
function unwrap(value){
 for(let i=0;i<3;i++){
  if(value?.success===false)throw Error(value.message||'本地二维码页面未准备好。');
  if(value&&typeof value==='object'&&Object.prototype.hasOwnProperty.call(value,'data')){value=value.data;continue;}
  if(typeof value==='string'){try{value=JSON.parse(value);continue;}catch(_){}}
  break;
 }
 return value;
}
async function decode(controller,path,options={}){
 if(!controller||typeof controller.evaluateJavascript!=='function')throw Error('当前 Operit 不支持本地二维码页面，请使用连接文件或粘贴连接码。');
 const key=controller.key||'aidoll-qr',id=Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,9);
 active.set(key,id);
 const cancelled=()=>active.get(key)!==id||options.cancelled?.();
 try{
 const raw=await Tools.Files.readBinary(path,'android');
 if(cancelled())throw Error('已取消二维码读取。');
 const bytes=raw.contentBase64||raw.data?.contentBase64;
 if(typeof bytes!=='string'||!bytes||bytes.length>Math.ceil(4*1024*1024/3)*4||!/^[A-Za-z0-9+/=]+$/.test(bytes))throw Error('图片超过4MB或未提供可读取的二进制内容，请裁剪二维码截图后重试。');
 const mime=/^iVBOR/.test(bytes)?'image/png':/^UklGR/.test(bytes)?'image/webp':/^\/9j\//.test(bytes)?'image/jpeg':null;
 if(!mime)throw Error('请选择PNG、JPEG或WebP二维码图片。');
 await controller.evaluateJavascript('window.aiDollQR && window.aiDollQR.start('+JSON.stringify('data:'+mime+';base64,'+bytes)+','+JSON.stringify(id)+')');
 const until=Date.now()+12000;
  while(Date.now()<until){
   if(cancelled())throw Error('已取消二维码读取。');
   const result=unwrap(await controller.evaluateJavascript('window.aiDollQR ? window.aiDollQR.state() : null'));
   if(result?.id===id&&result.state==='done')return result.text;
   if(result?.id===id&&result.state==='error')throw Error(result.error||'二维码读取失败。');
   if(result?.state==='cancelled')throw Error('已取消二维码读取。');
   await Tools.System.sleep(120);
  }
  throw Error('二维码读取超时，请重新选择清晰图片，或使用连接文件／连接码。');
 }finally{if(active.get(key)===id)active.delete(key);}
}
async function cancel(controller){
 active.delete(controller?.key||'aidoll-qr');
 if(controller?.evaluateJavascript)try{await controller.evaluateJavascript('window.aiDollQR && window.aiDollQR.cancel()');}catch(_){}
}
exports.html=html;exports.decode=decode;exports.cancel=cancel;exports.unwrap=unwrap;
