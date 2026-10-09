#pragma once
// Generated from tools/ota_manager.js.
static const char OTA_MANAGER_JS[] PROGMEM=R"OTA_JS(/* Device settings: explicit, local firmware selection; no remote downloads. */
(() => {
  let busy = false;
  const button = document.getElementById('upgradeFirmware');
  const hint = document.getElementById('otaResult');
  const bar = document.getElementById('otaProgress');
  button.onclick = async () => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    let ticket = '';
    let committed = false;
    try {
      const file = document.getElementById('otaFile').files[0];
      const manifestFile = document.getElementById('otaManifest').files[0];
      if (!file || !manifestFile) throw Error('请同时选择 firmware.bin 和 FLASH_MANIFEST.json。');
      if (file.size < 288 || file.size > 1310720 || manifestFile.size > 8192) throw Error('文件大小不适合本设备。');
      const manifest = JSON.parse(await manifestFile.text());
      const matches = (manifest.images || []).filter(item => item.file === 'firmware.bin');
      if (manifest.chip !== 'esp32c3' || manifest.target !== 'ai-doll-supermini-v1' || matches.length !== 1 ||
          matches[0].bytes !== file.size || !/^[a-f0-9]{64}$/.test(matches[0].sha256) ||
          !/^doll-lab-/.test(manifest.firmware || '')) throw Error('固件清单不匹配。');
      const data = new Uint8Array(await file.arrayBuffer());
      if (data[0] !== 0xe9 || data[12] !== 5 || data[13] !== 0 ||
          data[32] !== 0x32 || data[33] !== 0x54 || data[34] !== 0xcd || data[35] !== 0xab) throw Error('请选择 ESP32-C3 应用固件，不要选择合并烧录文件。');
      if (!window.confirm('安装 ' + manifest.firmware + '？升级期间暂停触摸采样并关闭震动输出，保留网络、通道和日志。请保持供电。')) {
        hint.textContent = '已取消，未写入设备。';
        return;
      }
      const before = await api('/api/status');
      bar.hidden = false;
      bar.value = 0;
      hint.textContent = '正在上传并校验…';
      const start = await api('/api/ota', {action: 'start', confirmed: true, target: manifest.target,
        chip: manifest.chip, bytes: file.size, sha256: matches[0].sha256});
      ticket = start.ticket;
      for (let offset = 0; offset < data.length; offset += 3072) {
        const chunk = data.subarray(offset, offset + 3072);
        const reply = await api('/api/ota', {action: 'chunk', ticket, offset,
          data: btoa(String.fromCharCode(...chunk))});
        if (reply.received_bytes !== offset + chunk.length) throw Error('上传进度不一致。');
        bar.value = Math.round(reply.received_bytes * 100 / data.length);
      }
      await api('/api/ota', {action: 'finish', ticket});
      committed = true;
      hint.textContent = '校验通过，设备重启中；等待新固件启动确认…';
      const deadline = Date.now() + 90000;
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        let state;
        try { state = await api('/api/status'); } catch (_) { continue; }
        if (state.boot_id !== before.boot_id && !state.ota.pending_verification) {
          if (state.firmware !== manifest.firmware) throw Error('设备启动了其他版本，可能已回滚。请检查状态。');
          hint.textContent = '升级完成：' + state.firmware + '，配置已保留。';
          return;
        }
      }
      throw Error('上传完成，但尚未确认新固件启动。请检查设备地址和状态，勿立即重复升级。');
    } catch (error) {
      if (ticket && !committed) {
        try { await api('/api/ota', {action: 'abort', ticket}); } catch (_) { /* Commit reply may have been lost. */ }
      }
      hint.textContent = error.message + ' 如上传中断，30 秒后自动取消；若提交响应丢失，请先刷新检查版本。';
    } finally {
      busy = false;
      button.disabled = false;
    }
  };
})();
)OTA_JS";
