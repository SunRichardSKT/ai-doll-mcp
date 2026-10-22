// A bounded phone worker owns collection; a model reply never owns the clock.
const store=require('./settings.js'),interaction=require('./interaction.js'),recovery=require('./recovery.js');
async function run(p){
  const deadline=Date.now()+(p.duration_sec||240)*1000;
  let added=0,attempt=0,tool;
  while(Date.now()<deadline){
    await p.ensure_active();
    const cfg=await store.config();
    const journal=cfg.binding?await store.read('delivery_'+cfg.binding+'.json'):null;
    if((cfg.continuous_enabled||cfg.active_reply_requested)&&journal?.pending?.phase!=='sending')return {state:'continued',synchronized:true,added,switch_to:'interaction'};
    if(!cfg.auto_sync_enabled||cfg.sync_paused)return {state:'disabled',synchronized:true,added};
    try{
      tool=tool||await interaction.connect(p.mcp_url,p.connection);
      const result=await tool('_sync_records');added+=result.added||0;attempt=0;
      const fast=result.sync?.archive_lease_supported&&!result.sync?.compatibility_copy_only&&
        result.sync?.pending_records>0&&result.sync?.last_page_progress;
      await Tools.System.sleep(fast?100:1500);
    }catch(error){
      if(!recovery.retryable(error))throw error;
      const pause=Math.min(recovery.delay(attempt++),Math.max(0,deadline-Date.now()));
      if(p.on_error)await p.on_error(error,pause);
      // Sleep in short pieces so a user's stop is observed during backoff too.
      let remaining=pause;while(remaining>0){await p.ensure_active();const step=Math.min(1000,remaining);await Tools.System.sleep(step);remaining-=step;}
    }
  }
  return {state:'continued',synchronized:true,added};
}
exports.run=run;
