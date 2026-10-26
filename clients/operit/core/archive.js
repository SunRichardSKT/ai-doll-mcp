// Immutable, checked archive segments are the source of truth. The hot index is
// expendable; a successful write is not claimed to be a filesystem fsync.
const store=require('./settings.js');
const archives=new Map();
function checksum(value){
  const text=JSON.stringify(value);let hash=2166136261;
  for(let i=0;i<text.length;i++){hash^=text.charCodeAt(i);hash=Math.imul(hash,16777619);}
  return (hash>>>0).toString(16).padStart(8,'0');
}
function create(c){
  if(archives.has(c.storage_key))return archives.get(c.storage_key);
  const prefix='device_'+c.storage_key+'_';
  const read=(n,d)=>store.read(prefix+n+'.json',d),write=(n,v)=>store.write(prefix+n+'.json',v);
  let recovered=null,catalog=new Set(),dailyCounts=new Map(),tail=Promise.resolve();
  const serial=fn=>{const next=tail.then(fn,fn);tail=next.catch(()=>{});return next;};
  async function all(){
    let names=[];
    if(typeof Tools.Files.list==='function')names=await store.listNames(prefix);
    names=names.filter(n=>n.startsWith(prefix+'segment_')||n.startsWith(prefix+'commit_')||n.startsWith(prefix+'history_'));
    const present=new Set(names),rebuild=!recovered||[...catalog].some(n=>!present.has(n));
    const changed=rebuild?names:names.filter(n=>!catalog.has(n));
    if(!rebuild&&!changed.length)return recovered;
    const byKey=new Map();
    for(const e of rebuild?(await index()).events||[]:recovered)byKey.set(e.event_id||'legacy:'+e.id,e);
    // A commit arriving after its segment must also cause the pair to be read.
    const files=new Set(changed.map(n=>n.replace(prefix+'commit_',prefix+'segment_')));
    for(const name of files){
      if(name.startsWith(prefix+'history_')){
        let day;try{day=await store.read(name);}catch(_){continue;}
        dailyCounts.set(name,(day.events||[]).length);
        for(const e of day.events||[])byKey.set(e.event_id||'legacy:'+e.id,e);
      }else if(name.startsWith(prefix+'segment_')){
        let value,commit;try{value=await store.read(name);commit=await store.read(name.replace(prefix+'segment_',prefix+'commit_'));}catch(_){continue;}
        if(value?.schema!==1||value.data?.device_id!==c.device_id||value.checksum!==checksum(value.data)||!Array.isArray(value.data?.events)||
          commit?.schema!==1||commit.segment!==name.slice(prefix.length,-5)||commit.checksum!==value.checksum)continue;
        for(const e of value.data.events){
          const old=byKey.get(e.event_id);if(!old||old.delivery_quality==='offline_replay')byKey.set(e.event_id,e);
        }
      }
    }
    catalog=present;recovered=[...byKey.values()].sort((a,b)=>a.id-b.id);return recovered;
  }
  async function index(){
    let value,receipt,badIndex=false;
    try{value=await read('events');if(value&&(!Array.isArray(value.events)||!Array.isArray(value.seen)||!Array.isArray(value.receipts)))throw Error('bad index');}catch(_){value=null;badIndex=true;}
    try{receipt=await read('receipt_state');if(receipt&&(!Array.isArray(receipt.seen)||!Array.isArray(receipt.receipts)))receipt=null;}catch(_){}
    if(value)return {...value,...(receipt?{seen:receipt.seen,receipts:receipt.receipts}:{})};
    const names=typeof Tools.Files.list==='function'?await store.listNames(prefix):[];
    const previous=badIndex||names.some(n=>n.startsWith(prefix+'segment_')||n.startsWith(prefix+'history_'));
    return {schema:1,next_id:1,events:[],seen:receipt?.seen||[],receipts:receipt?.receipts||[],last_sync:null,
      delivery_recovery_required:previous&&!receipt,index_rebuilt:previous};
  }
  async function writeIndex(value){
    await store.checkedWrite(prefix+'receipt_state.json',{schema:1,seen:value.seen||[],receipts:value.receipts||[]});
    await store.checkedWrite(prefix+'events.json',value);
  }
  async function updateIndex(change){return await serial(async()=>{const value=await index(),before=JSON.stringify(value),result=await change(value);if(JSON.stringify(value)!==before)await writeIndex(value);return result;});}
  async function ingest(batch,{session=null,live=false,persistent=false}={}){
    return await serial(async()=>{
      const records=await all(),a=await index(),sync=await read('sync',{}),stamp=Date.now()/1000;
      if(typeof batch.boot_id!=='string'||!batch.boot_id||!Number.isFinite(batch.uptime_ms)||batch.uptime_ms<0||
        (persistent&&(!Array.isArray(batch.persistent_events)||typeof batch.event_storage?.storage_epoch!=='string'||!batch.event_storage.storage_epoch)))
        throw Error('设备归档批次无效，未确认缓存。');
      const anchors={...sync.anchors};
      if(!Number.isFinite(anchors[batch.boot_id]))anchors[batch.boot_id]=stamp-batch.uptime_ms/1000;
      const byKey=new Map(records.filter(e=>e.event_id).map(e=>[e.event_id,e]));
      let next=records.reduce((n,e)=>Math.max(n,(e.id||0)+1),a.next_id||1);
      const added=[],pageEvents=[];
      const entries=persistent?(batch.persistent_events||[]).map(e=>({raw:e.event,boot:e.boot_id,storage_id:e.storage_id})):
        (batch.events||[]).map(e=>({raw:e,boot:batch.boot_id}));
      let lastStorage=0;
      for(const entry of entries){
        const raw=entry.raw,boot=entry.boot;
        if(!raw||!Number.isInteger(raw.seq)||raw.seq<1||typeof boot!=='string'||!boot||!Number.isFinite(raw.uptime_ms)||raw.uptime_ms<0)
          throw Error('设备归档事件身份或时间无效，未确认缓存。');
        if(persistent&&(!Number.isSafeInteger(entry.storage_id)||entry.storage_id<=lastStorage))throw Error('持久事件游标顺序无效。');
        lastStorage=entry.storage_id||lastStorage;
        const key=c.device_id+':'+boot+':'+raw.seq;
        if(byKey.has(key)){pageEvents.push(byKey.get(key));continue;}
        let at=null,quality='unknown';
        if(raw.time_quality==='device_clock'&&Number.isFinite(raw.device_time_ms)&&raw.device_time_ms>=1704067200000&&raw.device_time_ms<=4102444800000){at=raw.device_time_ms/1000;quality='device_clock';}
        else if(Number.isFinite(anchors[boot])){at=anchors[boot]+raw.uptime_ms/1000;quality='estimated_from_boot_anchor';}
        const age=boot===batch.boot_id?(batch.uptime_ms-raw.uptime_ms)/1000:Infinity;
        const inSession=session&&session.boot===boot&&raw.seq>session.boundary;
        const current=live&&!persistent&&!batch.gap&&0<=age&&age<=30&&(!session||inSession);
        const event={...raw,id:next++,event_id:key,device_id:c.device_id,boot,boot_id:boot,at,time_quality:quality,
          session_id:inSession?session.id:null,delivery_quality:current?'live':'offline_replay',received_at:stamp,
          ...(entry.storage_id?{storage_id:entry.storage_id,storage_epoch:batch.event_storage?.storage_epoch}:{})};
        byKey.set(key,event);added.push(event);pageEvents.push(event);
      }
      if(persistent&&((batch.storage_cursor||0)!==lastStorage))throw Error('补传页游标与记录不符，未确认缓存。');
      if(added.length||(persistent&&pageEvents.length)){
        const snapshot=persistent?pageEvents:added;
        const data={device_id:c.device_id,events:snapshot},digest=checksum(data);
        const suffix=snapshot[0].id+'_'+snapshot[snapshot.length-1].id+'_'+digest;
        const segment=prefix+'segment_'+suffix+'.json';
        let existing;try{existing=await store.read(segment);}catch(_){}
        if(!existing||existing.checksum!==digest||checksum(existing.data)!==digest)
          await store.checkedWrite(segment,{schema:1,data,checksum:digest});
        else if(JSON.stringify(existing.data)!==JSON.stringify(data))throw Error('归档页校验不一致，未确认设备副本。');
        const commit=prefix+'commit_'+suffix+'.json';
        await store.checkedWrite(commit,{schema:1,segment:'segment_'+suffix,checksum:digest});
        catalog.add(segment);catalog.add(commit);
        recovered=[...byKey.values()].sort((x,y)=>x.id-y.id);
        // Daily files are compatibility checkpoints, not the authoritative tail.
        // Read/commit immutable segments first; do not rewrite a whole day per touch.
        for(const day of new Set(added.map(e=>Number.isFinite(e.at)?new Date(e.at*1000).toISOString().slice(0,10).replace(/-/g,''):'unknown'))){
          const filename=prefix+'history_'+day+'.json';
          const events=recovered.filter(e=>(Number.isFinite(e.at)?new Date(e.at*1000).toISOString().slice(0,10).replace(/-/g,''):'unknown')===day);
          if(!dailyCounts.has(filename)||events.length-dailyCounts.get(filename)>=128){
            await store.checkedWrite(filename,{schema:1,events});
            dailyCounts.set(filename,events.length);catalog.add(filename);
          }
        }
      }
      a.events=(recovered||records).slice(-2000);a.next_id=next;a.last_sync=stamp;
      if(!persistent){a.boot=batch.boot_id;a.cursor=batch.next_cursor;}
      await writeIndex(a);
      const updated={...sync,anchors,last_sync:stamp,boot_id:batch.boot_id,
        ...(persistent?{storage_epoch:batch.event_storage?.storage_epoch,storage_cursor:batch.storage_cursor}:{}),
        pending_records:batch.event_storage?.pending_records??sync.pending_records??0,
        lost_records:batch.event_storage?.lost_records??sync.lost_records??0,
        corrupt_records:batch.event_storage?.corrupt_records??sync.corrupt_records??0,
        write_failures_since_boot:batch.event_storage?.write_failures_since_boot??sync.write_failures_since_boot??0};
      await store.checkedWrite(prefix+'sync.json',updated);
      return {added:added.length,cursor:batch.storage_cursor||0,commit_verified:true,archive:a,sync:updated};
    });
  }
  async function query(args={}){
    // Rebuilding the history cache must not race a committing live page.
    return await serial(async()=>{
    const after=args.after??0,limit=args.limit??50;
    if(!Number.isSafeInteger(after)||after<0||!Number.isInteger(limit)||limit<1||limit>200)throw Error('历史游标或页大小无效。');
    let records=await all();
    if(args.date==='unknown'||args.unknown_time===true)records=records.filter(e=>!Number.isFinite(e.at));
    else if(args.date){
      if(!/^\d{4}-\d{2}-\d{2}$/.test(args.date))throw Error('日期格式为YYYY-MM-DD。');
      const start=new Date(args.date+'T00:00:00'),end=new Date(start);end.setDate(end.getDate()+1);
      const [year,month,day]=args.date.split('-').map(Number);
      if(!Number.isFinite(start.getTime())||start.getFullYear()!==year||start.getMonth()+1!==month||start.getDate()!==day)
        throw Error('日期无效，请填写实际存在的日期。');
      records=records.filter(e=>Number.isFinite(e.at)&&e.at>=start.getTime()/1000&&e.at<end.getTime()/1000);
    }
    const page=records.filter(e=>e.id>after).sort((x,y)=>x.id-y.id),selected=page.slice(0,limit),sync=await read('sync',{});
    return {events:selected,has_more:page.length>limit,next_cursor:selected[selected.length-1]?.id??after,
      history_source:'android_local',scope:args.date?'daily_archive':'durable_archive',last_sync:sync.last_sync||(await index()).last_sync,
      durable_history:'checked_segments_in_plugin_directory',recording_scope:'while_record_sync_or_interaction_runs'};
    });
  }
  const api={ingest,query,index,updateIndex,all};archives.set(c.storage_key,api);return api;
}
exports.create=create;exports.checksum=checksum;
