/* Local browser pairing UI. qrcodegen is bundled ahead of this file; no CDN. */
(function(root){
  'use strict';
  function code(value){
    const bytes=new TextEncoder().encode(JSON.stringify(value));
    let text='';for(const byte of bytes)text+=String.fromCharCode(byte);
    return 'AIDOLL1:'+btoa(text).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  }
  function deviceConnection(status,setup){
    if(!status.wifi_connected||!status.ip||status.ip==='0.0.0.0')throw Error('请先完成家庭 Wi-Fi 配网，再生成手机连接。');
    if(!setup.enabled||!setup.token)throw Error('请先开启设备 MCP。');
    if(status.remote_server?.enabled)throw Error('设备已开启直传，请在服务器管理页获取 Operit 连接。');
    return {schema:1,kind:'ai-doll-device-connection',mode:'phone',
      mcp_url:'http://'+status.ip+'/mcp',token:setup.token,device_id:status.device_id,
      hostname:status.hostname,label:status.device_name||status.device_id};
  }
  function qrSVG(value){
    if(!root.qrcodegen)throw Error('本地二维码资源未加载，请使用连接文件。');
    const qr=root.qrcodegen.QrCode.encodeText(value,root.qrcodegen.QrCode.Ecc.MEDIUM);
    const border=4,path=[];
    for(let y=0;y<qr.size;y++)for(let x=0;x<qr.size;x++)if(qr.getModule(x,y))path.push('M'+(x+border)+','+(y+border)+'h1v1h-1z');
    const size=qr.size+border*2;
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+size+' '+size+'" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/><path d="'+path.join(' ')+'" fill="black"/></svg>';
  }
  function download(value,filename){
    const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=filename||'AI_Doll_Operit_Connection.json';
    document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function render(container,connection){
    container.replaceChildren();
    const value=code(connection),note=document.createElement('p'),message=document.createElement('p'),
      text=document.createElement('textarea'),image=document.createElement('img');
    note.textContent='同一部手机可下载连接文件，在 Operit 导入，或复制连接码。二维码由本页临时生成，无需在设备上贴标签。';
    text.value=value;text.readOnly=true;text.hidden=true;text.rows=5;
    text.setAttribute('aria-label','Operit 连接码');text.style.cssText='width:100%;box-sizing:border-box;overflow-wrap:anywhere';
    image.hidden=true;image.alt='AI Doll 临时连接二维码';image.style.cssText='display:none;width:min(320px,100%);height:auto;background:white';
    function button(label,action){const b=document.createElement('button');b.type='button';b.textContent=label;
      b.onclick=async()=>{try{message.textContent='';await action();}catch(e){message.textContent=e.message||String(e);}};return b;}
    const save=button('下载手机连接文件',()=>download(connection));
    const copy=button('复制连接码',async()=>{
      text.hidden=false;
      try{await navigator.clipboard.writeText(value);message.textContent='连接码已复制，在 Operit 的添加娃娃页面粘贴即可。';}
      catch(_){text.focus();text.select();message.textContent='请复制已选中的连接码，在 Operit 中粘贴。';}
    });
    const show=button('显示临时二维码',()=>{
      image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(qrSVG(value));image.hidden=false;image.style.display='block';
      message.textContent='可从另一块屏幕拍照识别；只有一部手机时保存或截图后，在 Operit 选择相册图片。';
    });
    container.append(note,save,copy,show,text,image,message);
  }
  root.AIDollPairing={code,deviceConnection,qrSVG,render,download};
  if(typeof module==='object'&&module.exports)module.exports=root.AIDollPairing;
})(typeof globalThis==='object'?globalThis:this);
