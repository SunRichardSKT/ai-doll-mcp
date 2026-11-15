/* Local management only. AI responses remain in the user's existing chat. */
(() => {
  const el = id => document.getElementById(id);
  let currentView = 'overview', currentStep = 0, state = null, frame = null, framePanel = '';
  let busy = false, configText = '', firstState = true, lastJobMessage = '', usbWifiOpen=false;
  el('pairForm').append(el('pairTemplate').content.cloneNode(true));
  el('secureForm').append(el('secureTemplate').content.cloneNode(true));

  async function api(path, data) {
    const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.PANEL_CSRF},
      body: data === undefined ? undefined : JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || '请求未完成，请重试。');
    return result;
  }
  for(const id of ['openDevice','upgradeLink'])el(id).onclick=async event=>{
    if(!state?.collector?.running||state.collector.collector_error)return;
    event.preventDefault();const target=window.open('about:blank','_blank');
    try{const entry=await api('/api/device-settings');if(target){target.opener=null;target.location.href=entry.url;}else notice('请允许弹出设备设置窗口。',true);}
    catch(error){if(target)target.close();notice(error.message,true);}
  };
  function toast(message) {
    el('toast').textContent = message;
    el('toast').hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el('toast').hidden = true; }, 2600);
  }
  function notice(message, error = false) {
    el('globalNotice').textContent = message;
    el('globalNotice').className = 'notice' + (error ? ' error' : '');
    el('globalNotice').hidden = !message;
  }
  function setBusy(value) {
    for (const button of document.querySelectorAll('[data-action], #installClaude, #downloadLocalConfig, #operitStart, #operitConnection, #operitToolpkg, #pairButton, #connectUsb, #autoPairUsb, #saveSecure, #saveStartSecure, #verifyChat, #saveStartup, #checkStartup, #upgradeSelected, #upgradeBundled')) button.disabled = value;
  }
  async function copy(text) {
    if (!text) throw Error('请先完成配置。');
    await navigator.clipboard.writeText(text);
    toast('已复制');
  }
  function checklist() {
    const items = [
      [state.environment_ready, '电脑环境已准备', '准备电脑运行环境'],
      [state.paired || state.connection.transport === 'usb', '设备已配对 / 已选择 USB', '通过 Wi-Fi 配对设备'],
      [state.collector.running, '电脑采集正在运行', '启动电脑采集服务'],
      ...(el('hostChoice').value==='secure'?[
        [state.secure.tunnel_connected, 'ChatGPT 隧道检查通过', '检查 ChatGPT 隧道连接'],
        [state.secure.ordinary_chat_status_verified, '本次服务的 Chat 状态调用已核对', '在原聊天实际调用工具']
      ]:el('hostChoice').value==='operit'?[[state.operit?.running,'Operit 电脑连接服务已启动','手机独立连接，或启动 Operit 电脑连接服务']]:[])
    ];
    el('checklist').replaceChildren(...items.map(([done, yes, no]) => {
      const li = document.createElement('li'), badge = document.createElement('span');
      badge.className = 'pill' + (done ? '' : ' pending');
      badge.textContent = done ? '完成' : '待完成';
      li.append(badge, document.createTextNode(done ? yes : no));
      return li;
    }));
  }
  function render() {
    if (!state) return;
    const local = state.collector, cfg = state.secure_config, remote = state.secure;
    el('serviceDot').className = 'status-dot' + (local.running ? ' online' : '');
    el('serviceLabel').textContent = local.running ? '本机采集运行中' : '本机采集未启动';
    el('collectorMetric').textContent = local.running ? '运行中' : state.environment_ready ? '未启动' : '待安装';
    const recentlySynced = local.last_sync && Date.now()/1000-local.last_sync < 15;
    el('collectorDetail').textContent = local.collector_error ? (local.transport === 'usb' ? 'USB 暂未响应；已配网设备可点击搜索恢复' : '正在等待设备重连；已存历史可查询') : local.last_sync ? '最近同步：' + new Date(local.last_sync * 1000).toLocaleString('zh-CN') : '等待同步 / 启动';
    el('deviceMetric').textContent = !state.paired && state.connection.transport !== 'usb' ? '待配对' : local.running ? (local.collector_error ? '同步异常' : recentlySynced ? '正在同步' : '等待设备') : '已保存连接';
    el('deviceDetail').textContent = (state.device_id || '尚未识别设备') + (local.device_ip ? ' · 设备 IP：'+local.device_ip : ' · 设备 IP 尚未确认');
    const fresh = remote.checked_at && Date.now() / 1000 - remote.checked_at < 60;
    el('tunnelMetric').textContent = !cfg.configured ? '待配置' : !fresh ? '待检查' : remote.tunnel_connected ? '已连接' : remote.runtime_running ? '正在连接' : '未启动';
    el('tunnelDetail').textContent = cfg.configured ? (cfg.profile + ' · ' + ((state.profile_counts || {status: 2, history: 9, interaction: 19})[cfg.profile]) + ' 个工具' + (fresh ? ' · '+(remote.connection_message||'') : ' · 点击检查状态')) : '本机客户端可直接使用 STDIO';
    el('environmentInfo').textContent = state.environment_ready ? '运行环境已就绪。可继续配对或日常启动。' : '需要准备运行环境。点击下面的按钮自动安装依赖。';
    el('projectPath').textContent = '运行目录：' + state.project;
    el('version').textContent = 'Bridge ' + state.version;
    el('connectionId').value = cfg.tunnel_id;
    const host = local.running && !local.collector_error ? local.device_ip : null;
    const deviceUrl = host ? 'http://' + host + '/' : 'http://192.168.4.1/';
    el('openDevice').href = deviceUrl;
    el('upgradeLink').href = deviceUrl;
    el('openDevice').textContent = host ? '设备设置 · '+host : '热点设置 · 需连接娃娃热点';
    el('deviceAddress').textContent = host ? '当前设备局域网 IP：'+host+' · 最近同步已确认；同一家庭网络可访问。' : '当前设备局域网 IP 尚未确认。先检查设备或搜索；192.168.4.1 仅连接娃娃热点时可用。';
    if(el('debugConnection').open)el('connectionDebug').textContent=JSON.stringify({device:local,local_mcp:remote.local_mcp_verified,tunnel:remote,operit:state.operit},null,2);
    if (firstState) {
      el('deviceHost').value = state.connection.device_host || '';
      el('serialPort').value = state.connection.serial_port || (state.serial_ports?.length===1?state.serial_ports[0].port:'');
      el('hostChoice').value=localStorage.getItem('ai-doll-host-route')||(cfg.configured?'secure':'');
      updateHostRoute();
      el('tunnelId').value = cfg.tunnel_id;
      el('toolProfile').value = cfg.profile;
      currentStep = state.environment_ready ? ((state.paired || state.connection.transport === 'usb') ? 2 : 1) : 0;
      firstState = false;
      showStep(currentStep);
      if (!state.environment_ready) navigate('setup');
    }
    const pending = busy || state.job.state === 'running';
    el('serialPorts').replaceChildren(...(state.serial_ports||[]).map(p=>{const o=document.createElement('option');o.value=p.port;o.label=p.label;return o;}));
    el('usbProgress').textContent=local.device_ip?'设备已联网：'+local.device_ip+'。可直接自动配对 Wi-Fi，无需再次填写密码。':local.transport==='usb'?'USB 已连接。请在下方配置家庭 Wi-Fi，看到已连接后点击“自动配对 Wi-Fi”。':'请先连接开发板；已联网设备将跳过 Wi-Fi 表单。';
    setBusy(pending);
    if (state.job.state === 'running') notice(state.job.message);
    if (state.job.state === 'error') notice(state.job.message, true);
    if (state.job.message !== lastJobMessage && state.job.state !== 'idle') {
      el('operationLog').textContent += '\n' + new Date().toLocaleTimeString('zh-CN') + ' · ' + state.job.message;
      lastJobMessage = state.job.message;
    }
    checklist();
    const op = state.operit || {};
    const staleHost = op.host && !(op.addresses || []).includes(op.host);
    el('operitStatus').textContent = op.error || (staleHost ? '原电脑地址 '+op.host+' 已不在当前网络。选择下面的可用地址并保存启动，再在手机 AI Doll 设置中修改电脑 IP，无需重新绑定聊天。' : op.running ? '手机连接服务正在运行。电脑 IP 改变后，在手机设置中修改电脑 IP 即可。' : '服务未启动。选择模式后点击保存并启动。');
    const options = (op.addresses || []).join('|');
    if (el('operitHost').dataset.options !== options) {
      el('operitHost').dataset.options = options;
      el('operitHost').replaceChildren(...(op.addresses || []).map(host => {
        const option = document.createElement('option'); option.value = host; option.textContent = host; return option;
      }));
      if (!op.addresses?.length) {
        const option = document.createElement('option'); option.value = ''; option.textContent = '未找到局域网，请先连接 Wi-Fi';el('operitHost').append(option);
      }
      if (op.host && op.addresses?.includes(op.host)) el('operitHost').value = op.host;
    }
    if (!el('operitMode').dataset.loaded && op.mode) {el('operitMode').value = op.mode;el('operitMode').dataset.loaded = 'true';}
    if (frame && !local.running) detachFrame();
    mountFrame();
  }
  async function refresh() {
    state = await api('/api/state');
    render();
    return state;
  }
  function handleResult(action, result) {
    if (action.startsWith('operit-')) el('operitStatus').textContent = result.error ||
      (result.protocol_connected ? 'MCP 已连接，19 个工具发现通过。手机后台回复请在原聊天验收。' : result.stopped ? '已停止手机连接，历史保留。' : '配置已保存。');
    if (action === 'client-config'||action==='claude-config') {
      configText = JSON.stringify(action==='claude-config'?result.config:result, null, 2);
      el('localConfig').textContent = configText;
      el('mcpLocalConfig').textContent = configText;
      toast(action==='claude-config'?'已写入，请完全退出并重开 Claude Desktop':'客户端配置已生成');
    }
    if (action === 'pair') {
      el('deviceToken').value = '';
      el('deviceAdminPassword').value = '';
      el('deviceCheckResult').textContent = '配对成功：' + result.device_id + '\nWi-Fi 地址：' + result.device_host;
    }
    if (action === 'collector-check') {
      const d = result.device || {};
      el('deviceCheckResult').textContent = JSON.stringify({device_id: d.device_id,
        firmware: d.version || d.firmware || d.firmware_version, wifi_connected: d.wifi_connected,
        sensor_mode: d.sensor_mode, physical_inputs_enabled: d.physical_inputs_enabled,
        physical_outputs_enabled: d.physical_outputs_enabled, device_error: result.device_error}, null, 2);
    }
    if (action === 'discover') {
      if (!result.found) throw Error('尚未找到已配对设备。请检查设备供电、同一局域网及 MCP 开关。');
      el('deviceHost').value = result.device_host;
      el('deviceCheckResult').textContent = '已验证：' + result.device_id + '\n当前地址：' + result.device_host;
    }
    if (action.startsWith('secure-') || ['daily-start','repair-connection'].includes(action)) {
      const s = result.secure || result;
      el('secureResult').textContent = s.connection_message || (s.tunnel_connected ? '本地工具发现与隧道连接已通过。请继续在原聊天验证工具调用。' : s.runtime_running ? '客户端运行中，隧道尚未连接，请稍后检查状态。' : '操作完成；点击“检查状态”查看当前连接。');
    }
    if (action === 'verify-chat') el('chatVerification').textContent = '两个编号与当前服务的完成记录匹配。状态调用验收通过；互动反馈与空闲唤醒另行验收。';
    if (action === 'startup') {
      el('startupEnabled').checked = result.enabled;
      el('startupResult').textContent = result.enabled ? '登录恢复日常服务已开启，下次 Windows 登录生效。' : '登录恢复日常服务已关闭。';
    }
    if (action === 'ota') el('otaResult').textContent = '升级完成，新启动版本已验证：' + result.firmware;
  }
  async function run(action, data = {}) {
    if(action==='client-config')data={...data,client:['deepseek','gemini','claude','claude_code'].includes(el('hostChoice').value)?el('hostChoice').value:'local'};
    if (busy || state?.job.state === 'running') throw Error('请等待当前操作完成。');
    busy = true;
    setBusy(true);
    render();
    notice('正在处理…');
    try {
      await api('/api/action', {action, data});
      for (;;) {
        await new Promise(resolve => setTimeout(resolve, 650));
        await refresh();
        if (state.job.state !== 'running') break;
      }
      if (state.job.state === 'error') throw Error(state.job.message);
      handleResult(action, state.job.result || {});
      notice(state.job.message || '操作完成。');
      return state.job.result;
    } finally {
      busy = false;
      render();
    }
  }
  function bind(id, fn) {
    el(id).addEventListener('click', async () => {
      try { await fn(); } catch (error) { notice(error.message, true); }
    });
  }
  async function downloadOperit(path, filename, json) {
    const response = await fetch(path, {headers:{'X-CSRF-Token':window.PANEL_CSRF}});
    if (!response.ok) throw Error((await response.json()).error || '下载未完成');
    const blob = json ? new Blob([JSON.stringify(await response.json(), null, 2)], {type:'application/json'}) : await response.blob();
    const url = URL.createObjectURL(blob), a = document.createElement('a');a.href = url;a.download = filename;a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  bind('operitStart', async () => {
    await run('operit-save', {mode:el('operitMode').value,host:el('operitHost').value});
    await run('operit-start');
  });
  bind('operitToolpkg', () => downloadOperit('/api/operit-toolpkg','AI_Doll_Operit.toolpkg',false));
  bind('operitConnection', () => downloadOperit('/api/operit-connection','AI_Doll_Connection.json',true));
  function showStep(index) {
    currentStep = Math.max(0, Math.min(3, index));
    for (const panel of document.querySelectorAll('[data-step-panel]')) panel.hidden = Number(panel.dataset.stepPanel) !== currentStep;
    for (const tab of document.querySelectorAll('[data-step]')) {
      tab.classList.toggle('active', Number(tab.dataset.step) === currentStep);
      tab.setAttribute('aria-selected', Number(tab.dataset.step) === currentStep ? 'true' : 'false');
    }
    el('stepBack').disabled = currentStep === 0;
    el('stepNext').textContent = currentStep === 3 ? (el('hostChoice').value==='deepseek'?'返回概览':'完成，返回概览') : '下一步';
    mountFrame();
  }
  function detachFrame() {
    frame?.remove();
    frame = null;
    framePanel = '';
  }
  function mountFrame(panelOverride) {
    const slot = document.querySelector('#view-' + currentView + ' [data-embed]');
    if (!slot || (currentView==='simulation'&&!el('developerPanel').open)) { detachFrame(); return; }
    const panel = panelOverride || slot.dataset.embed;
    if(panel==='wifi'&&(!usbWifiOpen||state?.collector.transport!=='usb'||(currentView==='setup'&&currentStep!==1))){detachFrame();return;}
    if (!state?.collector.running) {
      if (!slot.querySelector('.embed-empty')) {
        slot.replaceChildren();
        const note = document.createElement('div');
        note.className = 'embed-empty';
        note.textContent = '请先启动电脑采集服务。历史查询只需要电脑服务运行，不要求设备在线。';
        slot.append(note);
      }
      return;
    }
    if (frame && framePanel === panel) return;
    detachFrame();
    slot.replaceChildren();
    frame = document.createElement('iframe');
    frame.className = 'embed';
    frame.title = ({channels: '通道配置与校准', persona: '人设设置', preferences: '反馈偏好', history: '互动历史', simulation: '模拟与读数', maintenance: '离线缓存', wifi: 'USB 配网'})[panel];
    frame.src = 'http://127.0.0.1:8768/' + (panel === 'preferences' ? 'bridge' : panel === 'wifi' ? '' : 'companion') + '?panel=' + panel;
    framePanel = panel;
    slot.append(frame);
  }
  function navigate(view) {
    if (!document.getElementById('view-' + view)) return;
    if (view !== currentView) detachFrame();
    currentView = view;
    for (const panel of document.querySelectorAll('.view')) panel.hidden = panel.id !== 'view-' + view;
    for (const tab of document.querySelectorAll('[data-view]')) {
      if (tab.dataset.view === view) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
    }
    el('devicePairSlot').append(...el('pairForm').childNodes);
    if (view === 'setup') el('pairForm').append(...el('devicePairSlot').childNodes);
    el('mcpFormSlot').append(...el('secureForm').childNodes);
    if (view === 'setup') el('secureForm').append(...el('mcpFormSlot').childNodes);
    (view==='setup'?el('setupUsbSlot'):el('deviceUsbSlot')).append(el('usbControls'));
    (view==='setup'?el('setupOperitSlot'):el('view-operit')).append(el('operitControls'));
    mountFrame();
    location.hash = view;
  }
  for (const button of document.querySelectorAll('[data-view], [data-nav]')) button.onclick = () => {navigate(button.dataset.view || button.dataset.nav);if(button.dataset.stepTarget)showStep(Number(button.dataset.stepTarget));};
  for (const button of document.querySelectorAll('[data-step]')) button.onclick = () => showStep(Number(button.dataset.step));
  for (const button of document.querySelectorAll('[data-action]')) button.onclick = async () => {
    if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
    try { await run(button.dataset.action); } catch (error) { notice(error.message, true); }
  };
  bind('stepBack', () => showStep(currentStep - 1));
  bind('stepNext', () => {
    if (currentStep === 0 && !state.environment_ready) throw Error('请先准备电脑运行环境。');
    if (currentStep === 1 && !state.paired && state.connection.transport !== 'usb') throw Error('请先选择开发板完成 USB 配网及自动配对，或展开热点说明。');
    if (currentStep === 2 && !el('hostChoice').value) throw Error('请选择你正在使用的 AI 应用。');
    if (currentStep === 3) navigate('overview'); else showStep(currentStep + 1);
  });
  bind('pairButton', () => run('pair', {host: el('deviceHost').value, token: el('deviceToken').value, admin_user: el('deviceAdminUser').value, admin_password: el('deviceAdminPassword').value}));
  bind('connectUsb', async () => {
    await run('usb', {port: el('serialPort').value});
    if(state.collector.device_ip){await run('usb-pair-wifi',{port:el('serialPort').value});return;}
    usbWifiOpen=true;mountFrame('wifi');
  });
  bind('autoPairUsb', async () => {await run('usb-pair-wifi', {port: el('serialPort').value});usbWifiOpen=false;detachFrame();});
  bind('usbWifi', () => {
    if (state.collector.transport !== 'usb') throw Error('请先切换为 USB 连接。Wi-Fi 已连接时可直接打开设备设置页。');
    usbWifiOpen=true;
    mountFrame('wifi');
  });
  const secureData = () => ({tunnel_id: el('tunnelId').value, api_key: el('runtimeKey').value, profile: el('toolProfile').value});
  bind('saveSecure', async () => { await run('secure-save', secureData()); el('runtimeKey').value = ''; });
  bind('saveStartSecure', async () => {
    await run('secure-save', secureData());
    el('runtimeKey').value = '';
    await run('secure-start');
  });
  bind('verifyChat', () => run('verify-chat', {installation_call_id: el('installationCallId').value, device_call_id: el('deviceCallId').value}));
  bind('copyLocalConfig', () => copy(configText));
  bind('downloadLocalConfig', async()=>{
    await run('client-config');
    const url=URL.createObjectURL(new Blob([configText],{type:'application/json'})),link=document.createElement('a');
    link.href=url;link.download=el('hostChoice').value==='deepseek'?'AI_Doll_DSH.cordis.patch.yml':el('hostChoice').value==='claude_code'?'AI_Doll_Claude_Code.json':'AI_Doll_Local_MCP.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  bind('installClaude',()=>run('claude-config'));
  bind('copyCloudMcp',async()=>{
    let address;try{address=new URL(el('cloudMcpURL').value.trim());}catch{throw Error('请粘贴服务器设备卡片的完整 HTTPS MCP 地址。');}
    const host=address.hostname.toLowerCase(),ip=host.split('.').map(Number);
    const privateHost=host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host==='[::1]'||/^\[(fc|fd|fe80)/.test(host)||
      (/^\d+\.\d+\.\d+\.\d+$/.test(host)&&(ip[0]===0||ip[0]===10||ip[0]===127||ip[0]>=224||ip[0]===169&&ip[1]===254||ip[0]===192&&ip[1]===168||ip[0]===172&&ip[1]>=16&&ip[1]<=31));
    if(address.protocol!=='https:'||address.username||address.password||address.hash||address.search||privateHost||!address.pathname.endsWith('/mcp'))throw Error('远程连接请使用服务器的公网 HTTPS MCP 地址，包含完整私密路径；设备热点和本机地址不能用于云端连接。');
    if(el('hostChoice').value==='claude_http'&&address.port&&address.port!=='443')throw Error('Claude 远程连接需使用标准 HTTPS 443 端口。');
    await copy(address.href);notice('地址格式已核对并复制。请在所选 AI 中添加连接，再实际调用设备状态。');
  });
  bind('copyMcpConfig', () => copy(configText));
  bind('copyTunnel', () => copy(el('connectionId').value));
  bind('copyVerify', () => copy(el('verificationPrompt').value));
  bind('copyInteraction', () => copy(el('interactionPrompt').value));
  bind('saveStartup', () => run('startup', {action: el('startupEnabled').checked ? 'install' : 'remove'}));
  bind('checkStartup', () => run('startup', {action: 'status'}));
  async function upgrade(bundled) {
    if (!el('otaConfirmed').checked) throw Error('请先确认稳定供电并允许升级固件。');
    const data = {confirmed: true, bundled};
    if (!bundled) {
      const image = el('otaFile').files[0], manifest = el('otaManifest').files[0];
      if (!image || !manifest) throw Error('请选择 firmware.bin 和 FLASH_MANIFEST.json。');
      if (image.size > 0x140000 || manifest.size > 8192) throw Error('所选文件过大，不适合本设备。');
      const bytes = new Uint8Array(await image.arrayBuffer());
      let binary = '';
      for (let offset=0; offset<bytes.length; offset+=8192) binary += String.fromCharCode(...bytes.subarray(offset, offset+8192));
      data.image_base64 = btoa(binary);
      data.manifest = JSON.parse(await manifest.text());
    }
    el('otaResult').textContent = '正在校验、上传并等待新启动验证，请保持设备供电。';
    await run('ota', data);
    el('otaConfirmed').checked = false;
  }
  bind('upgradeSelected', () => upgrade(false));
  bind('upgradeBundled', () => upgrade(true));
  bind('personaTab', () => { document.querySelector('#view-persona [data-embed]').dataset.embed = 'persona'; mountFrame('persona'); });
  bind('preferencesTab', () => { document.querySelector('#view-persona [data-embed]').dataset.embed = 'preferences'; mountFrame('preferences'); });
  bind('exportDiagnostics', async () => {
    const report = await api('/api/diagnostics');
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'ai-doll-connection-diagnostics.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  });
  function updateHostRoute(){
    const route=el('hostChoice').value,secure=route==='secure',operit=route==='operit';
    const local=['local','claude','claude_code','deepseek','gemini'].includes(route),cloud=['chatgpt_http','claude_http','gemini_http'].includes(route);
    el('setupSecure').hidden = !secure;
    el('setupLocal').hidden = !local;
    el('setupOperit').hidden=!operit;
    el('chooseHostHint').hidden=!!route;
    el('setupCloud').hidden=!cloud;
    el('setupDeepSeek').hidden=!['deepseek','gemini'].includes(route);
    el('claudeLocalActions').hidden=route!=='claude';
    el('claudeCodeActions').hidden=route!=='claude_code';
    el('localClientHint').textContent=route==='claude'?'Claude Desktop 使用本机配置。可一键写入 ai_doll，或下载配置后合并到原 mcpServers 中；电脑采集需保持运行。':'生成配置后合并 ai_doll 项到客户端 MCP 设置，保留已有服务。电脑采集需保持运行。';
    if(route==='deepseek')el('localClientHint').textContent='DeepSeek DSH：生成原生 dsh-mcp-client 条目，合并到当前 profile 的 cordis.patch.yml；下载内容是合法 YAML 的 JSON 数组。保留其他条目，重启对应 profile 后调用设备状态。';
    if(route==='gemini')el('localClientHint').textContent='Gemini CLI：生成配置后合并 mcpServers.ai_doll 到用户目录 .gemini/settings.json；保留其他设置。重开 Gemini CLI，用 /mcp 查看连接并批准工具调用。';
    if(route==='claude_code')el('localClientHint').textContent='Claude Code（CLI）：下载专用配置，在文件保存目录打开终端，运行下方命令。保持电脑采集服务运行，在 Claude Code 中用 /mcp 检查 AI Doll 并批准工具调用。';
    if(['deepseek','gemini'].includes(route))el('setupDeepSeek').textContent=route==='deepseek'?'此路线适用于 DeepSeek 官方 Harness（DSH）的桌面、Web 或 CLI profile；不是普通 DeepSeek 聊天 App。使用 MCP 的是运行 DSH 的电脑。':'此路线适用于 Google 官方 Gemini CLI。Gemini 普通网页／手机 App 的扩展入口与 CLI 不同。';
    const claudeCloud=route==='claude_http';
    el('cloudHeading').textContent=claudeCloud?'Claude 网页与手机：远程连接':'ChatGPT：远程 HTTPS 连接';
    el('cloudInstructions').textContent=claudeCloud?'在 Claude 的连接器设置中添加自定义远程连接，粘贴完整地址；按本项目设备卡片选择无需登录，再在聊天中启用。':'在 ChatGPT Plugins 添加自定义 MCP，选择 Server URL，粘贴完整地址并按本项目设置选择无需身份验证；创建后安装并在聊天中启用。';
    el('cloudNetworkHint').textContent=claudeCloud?'连接由 Claude 云端发起，需要公网可达的 HTTPS 443 地址。设备热点、192.168…、127.0.0.1 和 OpenAI 隧道编号都不能填在这里。':'已有服务器可直接使用 HTTPS 地址；仅在电脑本机运行时选择 ChatGPT 私有隧道。';
    el('cloudOfficial').href=claudeCloud?'https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp':'https://developers.openai.com/api/docs/guides/custom-mcp-server';
    if(route==='gemini_http'){
      el('cloudHeading').textContent='Gemini 官方网页与手机：自定义应用';
      el('cloudInstructions').textContent='在 Gemini 网页 Settings → Connected Apps → Custom apps 添加完整 MCP 地址，按页面提示连接；在聊天输入 @ 选择该应用。首次添加在网页完成，连接后手机 App 也可使用。';
      el('cloudNetworkHint').textContent='需要公网 HTTPS 地址。Google 当前要求美国地区、18岁以上的个人账号、英文界面且开启 Keep Activity；没有入口时可选择 Gemini CLI。也可按官方指南使用 Gemini Apps Developer Mode。';
      el('cloudOfficial').href='https://support.google.com/gemini/answer/17209137?hl=en-45';
    }
    el('aiConnectionTitle').textContent=secure?'ChatGPT 隧道':'AI 接入方式';
    el('tunnelMetric').closest('article').hidden=!secure;
    document.querySelector('#view-overview [data-action="secure-status"]').hidden=!secure;
    el('verifyOperit').hidden=!operit;
    el('verifyMcp').hidden=operit||!route;
    el('verifyRouteHint').hidden=!!route;
    el('verifyRouteHint').textContent=route==='deepseek'?'DeepSeek 官方应用尚无已确认的自定义 MCP 连接步骤。请使用支持 MCP 的客户端，或在已有应用中桥接函数调用；不会将本页选择标记为连接成功。':'请返回上一步选择 AI 应用。';
    el('mcpVerifyHint').textContent=secure?'在 ChatGPT Plugins 添加自定义 MCP，选择隧道并填写下方 ID；安装后在聊天中启用，再调用设备状态。':route==='claude'?'完全退出并重新打开 Claude Desktop，在聊天中启用 AI Doll，再实际调用设备状态。':cloud?'在所选平台添加完整 HTTPS MCP 地址并启用，然后实际调用设备状态；能打开管理网页不代表 AI 已连接。':'在客户端合并本机配置并重新加载 MCP，再调用设备状态。';
    if(route==='claude_code')el('mcpVerifyHint').textContent='用专用配置启动 Claude Code，在 /mcp 查看 ai_doll，然后实际调用下方两个状态工具。';
    el('connectionId').closest('.copybox').hidden = !secure;
    el('chatVerification').closest('details').hidden = !secure;
    document.querySelector('[data-step-panel="3"] [data-action="secure-status"]').hidden = !secure;
    el('verificationPrompt').value = secure ? '请实际调用 get_installation_status 和 doll_get_status，返回设备状态及两个结果中的 verification.call_id。没有工具时如实说明，不用阅读文档代替调用。' : '请实际调用 ai_doll 的 get_installation_status 和 doll_get_status，返回采集服务、设备连接与模拟模式状态。没有工具时如实说明，不用阅读文档代替调用。';
    if(state)checklist();
  }
  el('hostChoice').onchange = () => {configText='';el('localConfig').textContent='请为所选客户端重新生成配置。';localStorage.setItem('ai-doll-host-route',el('hostChoice').value);updateHostRoute();};
  el('developerPanel').ontoggle=()=>mountFrame();
  el('debugConnection').ontoggle=()=>render();
  el('operitMode').insertAdjacentHTML('afterend','<label><input id=operitDeveloper type=checkbox>开发者：显示模拟演示模式</label>');
  el('operitDeveloper').onchange=()=>{const o=el('operitMode').querySelector('[value=simulation]');o.hidden=!el('operitDeveloper').checked;if(o.hidden&&el('operitMode').value==='simulation')el('operitMode').value='device';};
  refresh().then(() => { if (location.hash) navigate(location.hash.slice(1)); else if (!state.paired) { navigate('setup'); showStep(state.environment_ready ? 1 : 0); } }).catch(error => notice(error.message, true));
  setInterval(() => { if (!busy) refresh().catch(() => notice('管理服务暂不可用，请重新打开 AI_Doll.cmd。', true)); }, 4000);
})();
