/* Local management only. AI responses remain in the user's existing chat. */
(() => {
  const el = id => document.getElementById(id);
  let currentView = 'overview', currentStep = 0, state = null, frame = null, framePanel = '';
  let busy = false, configText = '', firstState = true, lastJobMessage = '';
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
    for (const button of document.querySelectorAll('[data-action], #pairButton, #connectUsb, #autoPairUsb, #saveSecure, #saveStartSecure, #verifyChat, #saveStartup, #checkStartup, #upgradeSelected, #upgradeBundled')) button.disabled = value;
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
      [state.secure.tunnel_connected, 'ChatGPT 隧道检查通过', state.secure_config.configured ? '检查 ChatGPT 隧道连接' : '使用普通 Chat 时配置 Secure 隧道'],
      [state.secure.ordinary_chat_status_verified, '本次服务的 Chat 状态调用已核对', '在原聊天实际调用工具；本机检查不替代 Chat 验证']
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
    el('collectorDetail').textContent = local.collector_error ? '设备同步暂不可用；已存历史可查询' : local.last_sync ? '最近同步：' + new Date(local.last_sync * 1000).toLocaleString('zh-CN') : '等待同步 / 启动';
    el('deviceMetric').textContent = !state.paired && state.connection.transport !== 'usb' ? '待配对' : local.running ? (local.collector_error ? '同步异常' : recentlySynced ? '正在同步' : '等待设备') : '已保存连接';
    el('deviceDetail').textContent = (state.device_id || '尚未识别设备') + (local.device_host || state.connection.device_host ? ' · ' + (local.device_host || state.connection.device_host) : '');
    const fresh = remote.checked_at && Date.now() / 1000 - remote.checked_at < 60;
    el('tunnelMetric').textContent = !cfg.configured ? '待配置' : !fresh ? '待检查' : remote.tunnel_connected ? '已连接' : remote.runtime_running ? '正在连接' : '未启动';
    el('tunnelDetail').textContent = cfg.configured ? (cfg.profile + ' · ' + ({status: 2, history: 9, interaction: 13}[cfg.profile]) + ' 个工具' + (fresh ? '' : ' · 点击检查状态')) : '本机客户端可直接使用 STDIO';
    el('environmentInfo').textContent = state.environment_ready ? '运行环境已就绪。可继续配对或日常启动。' : '需要准备运行环境。点击下面的按钮自动安装依赖。';
    el('projectPath').textContent = '运行目录：' + state.project;
    el('version').textContent = 'Bridge ' + state.version;
    el('connectionId').value = cfg.tunnel_id;
    const host = local.device_host || state.connection.device_host;
    const deviceUrl = host ? 'http://' + host + '/' : 'http://192.168.4.1/';
    el('openDevice').href = deviceUrl;
    el('upgradeLink').href = deviceUrl;
    if (firstState) {
      el('deviceHost').value = state.connection.device_host || '';
      el('serialPort').value = state.connection.serial_port || 'COM3';
      el('tunnelId').value = cfg.tunnel_id;
      el('toolProfile').value = cfg.profile;
      currentStep = state.environment_ready ? ((state.paired || state.connection.transport === 'usb') ? 2 : 1) : 0;
      firstState = false;
      showStep(currentStep);
      if (!state.environment_ready) navigate('setup');
    }
    const pending = busy || state.job.state === 'running';
    setBusy(pending);
    if (state.job.state === 'running') notice(state.job.message);
    if (state.job.state === 'error') notice(state.job.message, true);
    if (state.job.message !== lastJobMessage && state.job.state !== 'idle') {
      el('operationLog').textContent += '\n' + new Date().toLocaleTimeString('zh-CN') + ' · ' + state.job.message;
      lastJobMessage = state.job.message;
    }
    checklist();
    if (frame && !local.running) detachFrame();
    mountFrame();
  }
  async function refresh() {
    state = await api('/api/state');
    render();
    return state;
  }
  function handleResult(action, result) {
    if (action === 'client-config') {
      configText = JSON.stringify(result, null, 2);
      el('localConfig').textContent = configText;
      el('mcpLocalConfig').textContent = configText;
      toast('客户端配置已生成');
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
    if (action.startsWith('secure-') || action === 'daily-start') {
      const s = result.secure || result;
      el('secureResult').textContent = s.tunnel_connected ? '本地工具发现与隧道连接已通过。请继续在原聊天验证工具调用。' : s.runtime_running ? '客户端运行中，隧道尚未连接，请稍后检查状态。' : '操作完成；点击“检查状态”查看当前连接。';
    }
    if (action === 'verify-chat') el('chatVerification').textContent = '两个编号与当前服务的完成记录匹配。状态调用验收通过；互动反馈与空闲唤醒另行验收。';
    if (action === 'startup') {
      el('startupEnabled').checked = result.enabled;
      el('startupResult').textContent = result.enabled ? '登录自动采集已开启，下次 Windows 登录生效。' : '登录自动采集已关闭。';
    }
    if (action === 'ota') el('otaResult').textContent = '升级完成，新启动版本已验证：' + result.firmware;
  }
  async function run(action, data = {}) {
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
      notice('操作完成。');
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
  function showStep(index) {
    currentStep = Math.max(0, Math.min(3, index));
    for (const panel of document.querySelectorAll('[data-step-panel]')) panel.hidden = Number(panel.dataset.stepPanel) !== currentStep;
    for (const tab of document.querySelectorAll('[data-step]')) {
      tab.classList.toggle('active', Number(tab.dataset.step) === currentStep);
      tab.setAttribute('aria-selected', Number(tab.dataset.step) === currentStep ? 'true' : 'false');
    }
    el('stepBack').disabled = currentStep === 0;
    el('stepNext').textContent = currentStep === 3 ? '完成，返回概览' : '下一步';
  }
  function detachFrame() {
    frame?.remove();
    frame = null;
    framePanel = '';
  }
  function mountFrame(panelOverride) {
    const slot = document.querySelector('#view-' + currentView + ' [data-embed]');
    if (!slot) { detachFrame(); return; }
    const panel = panelOverride || slot.dataset.embed;
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
    mountFrame();
    location.hash = view;
  }
  for (const button of document.querySelectorAll('[data-view], [data-nav]')) button.onclick = () => navigate(button.dataset.view || button.dataset.nav);
  for (const button of document.querySelectorAll('[data-step]')) button.onclick = () => showStep(Number(button.dataset.step));
  for (const button of document.querySelectorAll('[data-action]')) button.onclick = async () => {
    if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
    try { await run(button.dataset.action); } catch (error) { notice(error.message, true); }
  };
  bind('stepBack', () => showStep(currentStep - 1));
  bind('stepNext', () => {
    if (currentStep === 0 && !state.environment_ready) throw Error('请先准备电脑运行环境。');
    if (currentStep === 1 && !state.paired && state.connection.transport !== 'usb') throw Error('请先完成设备配对，或在“设备连接”选择 USB 测试。');
    if (currentStep === 3) navigate('overview'); else showStep(currentStep + 1);
  });
  bind('pairButton', () => run('pair', {host: el('deviceHost').value, token: el('deviceToken').value, admin_user: el('deviceAdminUser').value, admin_password: el('deviceAdminPassword').value}));
  bind('connectUsb', () => run('usb', {port: el('serialPort').value}));
  bind('autoPairUsb', () => run('usb-pair-wifi', {port: el('serialPort').value}));
  bind('usbWifi', () => {
    if (state.collector.transport !== 'usb') throw Error('请先切换为 USB 连接。Wi-Fi 已连接时可直接打开设备设置页。');
    const slot = document.createElement('div');
    slot.dataset.embed = 'wifi';
    el('view-device').append(slot);
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
  el('hostChoice').onchange = () => {
    const secure = el('hostChoice').value === 'secure';
    el('setupSecure').hidden = !secure;
    el('setupLocal').hidden = secure;
    el('connectionId').closest('.copybox').hidden = !secure;
    el('chatVerification').closest('details').hidden = !secure;
    document.querySelector('[data-step-panel="3"] [data-action="secure-status"]').hidden = !secure;
    el('verificationPrompt').value = secure ? '请实际调用 get_installation_status 和 doll_get_status，返回设备状态及两个结果中的 verification.call_id。没有工具时如实说明，不用阅读文档代替调用。' : '请实际调用 ai_doll 的 get_installation_status 和 doll_get_status，返回采集服务、设备连接与模拟模式状态。没有工具时如实说明，不用阅读文档代替调用。';
  };
  refresh().then(() => { if (location.hash) navigate(location.hash.slice(1)); else if (!state.paired) { navigate('setup'); showStep(state.environment_ready ? 1 : 0); } }).catch(error => notice(error.message, true));
  setInterval(() => { if (!busy) refresh().catch(() => notice('管理服务暂不可用，请重新打开 AI_Doll.cmd。', true)); }, 4000);
})();
