// Shared engine for the unified ToolPkg; legacy standalone templates are frozen compatibility entries.
function chatId(value) {
  if(typeof value!=='string'||!value.trim()||value==='main'||value.length>128)
    throw Error('Provide the actual existing chat ID');
  return value;
}

async function inspect(id) {
  chatId(id);
  const found=await Tools.Chat.findChat({query:id,match:'exact',index:0});
  if(found.chat?.id!==id)throw Error('Saved chat ID was not confirmed');
  const listing=await Tools.Chat.listChats({query:id,match:'exact',limit:5});
  let recent=null,history_error=null;
  try { recent=await Tools.Chat.getMessages(id,{order:'desc',limit:10}); }
  catch(error) {history_error=String(error?.message||error);}
  return {chat_id:id,title:found.chat.title||'',current_chat_id:listing.currentChatId||null,
    is_current:listing.currentChatId===id,history_readable:Array.isArray(recent?.messages),history_error,
    recent_metadata:(recent?.messages||[]).map(m=>({sender:m.sender,timestamp:m.timestamp,
      provider:m.provider||null,model:m.modelName||null})),display_verified:false};
}

async function inspect_chat(p) { return await inspect(p.chat_id); }

async function write(path,data) {
  const result=await Tools.Files.write(path,JSON.stringify(data),false,'android');
  if(result.successful!==true)throw Error('Cannot save diagnostic state; message was not submitted');
}

async function send_probe(p) {
  const id=chatId(p.chat_id);
  if(p.workflow_confirmed!==true)throw Error('Run only from an independent user-started workflow');
  const timeout=p.timeout_sec===undefined?90:p.timeout_sec;
  if(!Number.isInteger(timeout)||timeout<30||timeout>120)throw Error('timeout_sec must be 30..120');
  const filename='ai_doll_chat_probe_'+id.replace(/[^a-zA-Z0-9_-]/g,'_')+'.json';
  const path=p.state_path||'/storage/emulated/0/Download/'+filename;
  if(typeof path!=='string'||!path.startsWith('/')||path.includes('..')||!/\/[^/]+\.json$/i.test(path))
    throw Error('Use a separate absolute JSON diagnostic file path');
  let stage='chat_binding',state=null;
  const report={diagnostic_complete:false,reply_returned:false,reply_nonce_matches:false,
    display_verified:false,automatic_retry:false,state_path:path};
  try {
    report.target=await inspect(id);
    stage='diagnostic_state';
    const exists=await Tools.Files.exists(path,'android');
    if(typeof exists.exists!=='boolean'||exists.isDirectory===true)throw Error('Cannot access diagnostic JSON file');
    if(exists.exists) {
      const prior=JSON.parse((await Tools.Files.read({path,environment:'android'})).content);
      if(prior.kind!=='operit-chat-probe'||prior.chat_id!==id)throw Error('File belongs to another use; choose a new diagnostic filename');
      if(prior.phase!=='completed') {
        return {...report,diagnostic_complete:true,blocked_by_prior_probe:true,
          probe_id:prior.probe_id,error:'Previous probe outcome is uncertain. Check that visible probe in the chat; no automatic resend.'};
      }
      return {...report,diagnostic_complete:true,already_completed:true,previous:prior.result};
    }
    const parent=path.slice(0,path.lastIndexOf('/'))||'/';
    const directory=await Tools.Files.exists(parent,'android');
    if(directory.exists!==true||directory.isDirectory===false)throw Error('Diagnostic parent directory must exist and be accessible');
    const probe='probe_'+Date.now()+'_'+Math.random().toString(16).slice(2,10);
    report.probe_id=probe;
    state={schema:1,kind:'operit-chat-probe',chat_id:id,probe_id:probe,phase:'sending'};
    await write(path,state);
    stage='main_chat_send';
    if (p.ensure_active) await p.ensure_active();
    const message='AI Doll 后台发送自检 '+probe+'。请只回复“后台连接正常 '+probe+'”，不要调用工具。';
    const started=Date.now();
    try {
      const reply=await Tools.Chat.sendMessage(message,id,undefined,undefined,
        {runtime:'main',persist_turn:true,hide_user_message:false,notify_reply:true,timeout_ms:timeout*1000});
      if(reply.chatId!==id)throw Error('Reply belongs to another chat');
      report.reply_returned=typeof reply.aiResponse==='string'&&!!reply.aiResponse.trim();
      report.reply_nonce_matches=report.reply_returned&&reply.aiResponse.includes(probe);
      if(!report.reply_returned)throw Error('No complete reply returned');
      state.phase='completed';
    } catch(error) {report.error=String(error?.message||error);}
    report.elapsed_ms=Date.now()-started;
    // Inspect persisted messages even after a timeout. A visible input is separate
    // from a model reply; persisted history is separate from a displayed message.
    stage='history_after';
    try {
      const history=await Tools.Chat.getMessages(id,{order:'desc',limit:20});
      const entries=(history.messages||[]).filter(m=>typeof m.content==='string'&&m.content.includes(probe));
      report.history_probe_present=entries.length>0;
      report.history_matching_senders=entries.map(m=>m.sender);
      report.history_ai_reply_present=entries.some(m=>/^(ai|assistant)$/i.test(m.sender)&&m.content.includes('后台连接正常 '+probe));
    } catch(error) {report.history_error=String(error?.message||error);}
    report.diagnostic_complete=true;
    state.result=report;
    stage='save_result';
    await write(path,state);
    return report;
  } catch(error) {throw Error('AI Doll probe ['+stage+']: '+String(error?.message||error));}
}

exports.inspect_chat=inspect_chat;
exports.send_probe=send_probe;
