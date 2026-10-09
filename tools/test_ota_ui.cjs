/* Isolated browser test: no owner device, history or firmware writes. */
const fs = require('fs'), path = require('path');
const {chromium} = require('playwright');
(async () => {
  const root = path.resolve(__dirname, '..');
  const source = fs.readFileSync(path.join(root, 'firmware/src/device_page.h'), 'utf8');
  const html = source.split('R"HTML(')[1].split(')HTML";')[0].replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, '');
  const executable = [chromium.executablePath(), 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
  const browser = await chromium.launch({headless: true, executablePath: executable});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.setContent(html);
    await page.evaluate(() => {
      window.testCalls = [];
      window.finished = false;
      window.api = async (path, body) => {
        window.testCalls.push({path, action: body?.action});
        if (path === '/api/status') return {boot_id: finished ? 'new-boot' : 'old-boot',
          firmware: 'doll-lab-2.7.0', ota: {pending_verification: false}};
        if (body.action === 'start') return {ticket: 'fixture-ticket', chunk_bytes: 3072};
        if (body.action === 'chunk') return {received_bytes: body.offset + atob(body.data).length};
        if (body.action === 'finish') { finished = true; return {ok: true}; }
        throw Error('Unexpected fixture action');
      };
    });
    await page.addScriptTag({path: path.join(root, 'tools/ota_manager.js')});
    await page.click('#upgradeFirmware');
    if (!(await page.textContent('#otaResult')).includes('同时选择')) throw Error('Missing files not explained');
    if (await page.evaluate(() => testCalls.length)) throw Error('Empty selection wrote API');
    const image = Buffer.alloc(4096); image[0] = 0xe9; image[12] = 5;
    Buffer.from('3254cdab', 'hex').copy(image, 32);
    const manifest = {target: 'ai-doll-supermini-v1', chip: 'esp32c3', firmware: 'doll-lab-2.7.0',
      images: [{file: 'firmware.bin', bytes: image.length, sha256: 'a'.repeat(64)}]};
    await page.setInputFiles('#otaFile', {name: 'firmware.bin', mimeType: 'application/octet-stream', buffer: image});
    await page.setInputFiles('#otaManifest', {name: 'FLASH_MANIFEST.json', mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(manifest))});
    page.once('dialog', dialog => dialog.dismiss());
    await page.click('#upgradeFirmware');
    await page.waitForFunction(() => document.querySelector('#otaResult').textContent.includes('已取消'));
    if (await page.evaluate(() => testCalls.length)) throw Error('Cancelled confirmation wrote API');
    page.once('dialog', dialog => dialog.accept());
    await page.click('#upgradeFirmware');
    await page.waitForFunction(() => document.querySelector('#otaResult').textContent.includes('升级完成'));
    const calls = await page.evaluate(() => testCalls);
    if (calls.filter(c => c.action === 'chunk').length !== 2 || calls.filter(c => c.action === 'finish').length !== 1) throw Error('Chunking/commit mismatch');
    if ((await page.locator('#otaProgress').evaluate(el => el.value)) !== 100) throw Error('Progress not complete');
    if (errors.length) throw Error(errors.join('\n'));
    await page.locator('#upgradeFirmware').scrollIntoViewIfNeeded();
    await page.screenshot({path: path.join(root, 'build/device-lab/ota-fixture-mobile.png')});
    console.log('PASS: isolated 390px OTA page, missing files, cancellation, chunks, progress and boot confirmation');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
