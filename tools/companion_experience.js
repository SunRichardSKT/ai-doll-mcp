/* Presentation-only configuration. Hardware editor remains separate. */
(async()=>{
  const section=document.createElement('section');section.id='feedback';
  section.innerHTML='<h2>日常陪伴</h2><p>继续原聊天的人设和话题，触摸自然融入回复。</p><label><input id="chatIntegration" type="checkbox"> 聊天时融入近期触摸</label><br><label><input id="proactiveFeedback" type="checkbox"> 允许触摸主动回应</label><p class="muted">主动开关不会自行启动聊天，仍需在支持事件的宿主中绑定当前聊天。普通 Chat 不承诺空闲唤醒。</p><label>语气 <input id="companionTone"></label><label>称呼 <input id="companionAddress"></label><button id="saveCompanionExperience">保存陪伴偏好</button><p id="experienceNote" role="status"></p>';
  const body=document.createElement('section');body.id='body';body.innerHTML='<h2>部位与回应方式</h2><p class="muted">这里仅改名称与回应方式，保留采样、校准和接线。轻回应只融入聊天，不单独主动回复；关闭后仍保存互动历史。</p><div id="bodyExperience" class="parts"></div>';
  const first=document.querySelector('section');first?.setAttribute('id','status');
  first?.after(section,body);
  const hardware=document.getElementById('parts')?.closest('section');hardware?.setAttribute('id','hardware');
  const text=(tag,value)=>{const element=document.createElement(tag);element.textContent=value;return element};
  const note=document.getElementById('experienceNote');
  try{
    const context=await tool('get_chat_context',{chat_id:'settings-panel'});
    document.getElementById('chatIntegration').checked=context.preferences.chat_integration_enabled;
    document.getElementById('proactiveFeedback').checked=context.preferences.proactive_enabled;
    document.getElementById('companionTone').value=context.feedback.tone;
    document.getElementById('companionAddress').value=context.feedback.preferred_address;
    document.getElementById('saveCompanionExperience').onclick=async()=>{
      try{await tool('update_companion_preferences',{changes:{chat_integration_enabled:document.getElementById('chatIntegration').checked,proactive_enabled:document.getElementById('proactiveFeedback').checked,feedback:{tone:document.getElementById('companionTone').value,preferred_address:document.getElementById('companionAddress').value}}});note.textContent='已保存；触摸反馈遵循已选人设来源，不修改原聊天设置。主动订阅需要在聊天宿主中开启。'}catch(error){note.textContent=error.message}
    };
    for(const channel of context.channels){
      const card=document.createElement('div');card.append(text('strong','CH'+channel.channel));
      const name=document.createElement('input');name.value=channel.name;name.setAttribute('aria-label','CH'+channel.channel+' 部位名称');
      const aliases=document.createElement('input');aliases.value=channel.aliases.join('、');aliases.placeholder='别名，用顿号分隔';aliases.setAttribute('aria-label','CH'+channel.channel+' 别名');
      const level=document.createElement('select');level.setAttribute('aria-label','CH'+channel.channel+' 回应方式');
      for(const [value,label]of[['off','不回应'],['light','轻回应，融入聊天'],['normal','正常回应']])level.add(new Option(label,value));level.value=channel.feedback_level;
      const hint=document.createElement('textarea');hint.value=channel.interaction_hint;hint.placeholder='可选：这个部位的互动偏好';hint.setAttribute('aria-label','CH'+channel.channel+' 互动提示');
      const save=text('button','保存此部位'),result=text('p','');save.type='button';
      save.onclick=async()=>{save.disabled=true;try{
        const changes={aliases:aliases.value.split('、').map(s=>s.trim()).filter(Boolean),feedback_level:level.value,interaction_hint:hint.value};
        if(name.value!==channel.name)changes.name=name.value;
        const response=await tool('update_body_part',{channel:channel.channel,changes});
        if(!response.updated)throw Error(response.message);channel.name=name.value;
        const legacyName=document.getElementById('part'+channel.channel);if(legacyName)legacyName.value=name.value;
        if(typeof channelDraft!=='undefined'){const saved=channelDraft.find(c=>c.channel===channel.channel);if(saved)saved.name=name.value;}
        result.textContent='已保存，采样和校准保持。';
      }catch(error){result.textContent=error.message}finally{save.disabled=false}};
      card.append(name,aliases,level,hint,save,result);document.getElementById('bodyExperience').append(card);
    }
  }catch(error){note.textContent='陪伴设置暂不可用：'+error.message}
})();
