/* Browser acceptance: wizard, real local service pages, navigation and responsive layout. */
const fs = require('fs'), path = require('path');
const {chromium} = require('playwright');
(async () => {
  const executable = [chromium.executablePath(), 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p => fs.existsSync(p));
  const browser = await chromium.launch({headless: true, executablePath: executable});
  const page = await browser.newPage({viewport: {width: 1360, height: 960}});
  const errors = [], failures = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => {if (r.status() >= 400 && !r.url().endsWith('favicon.ico') && !(r.status()===503 && r.url().includes(':8768/companion/tool'))) failures.push(r.status()+' '+r.url());});
  const output = path.resolve(__dirname, '../build/device-lab/gui-acceptance');
  fs.mkdirSync(output, {recursive: true});
  try {
    await page.goto(process.env.AI_DOLL_PANEL_URL || 'http://127.0.0.1:8769/');
    await page.waitForFunction(() => document.getElementById('deviceDetail').textContent !== '同一局域网，无需保持 USB');
    await page.click('[data-view="setup"]');
    for (let index=0; index<4; index++) {
      await page.click('[data-step="'+index+'"]');
      if (!(await page.locator('[data-step-panel="'+index+'"]').isVisible())) throw Error('Wizard step unavailable '+index);
    }
    await page.click('[data-step="2"]');
    await page.selectOption('#hostChoice', 'local');
    await page.click('#setupLocal [data-action="client-config"]');
    await page.waitForFunction(() => document.getElementById('localConfig').textContent.includes('mcpServers'));
    const config = JSON.parse(await page.textContent('#localConfig'));
    if (!path.isAbsolute(config.mcpServers.ai_doll.command)) throw Error('STDIO config must use absolute paths');
    await page.selectOption('#hostChoice', 'secure');
    await page.click('[data-view="device"]');
    if (!(await page.locator('#deviceHost').isVisible())) throw Error('Pair form missing after navigation');
    for (const [view, selectors] of [['channels', ['#parts']], ['persona', ['#persona']], ['history', ['#history', '#historyManagement']], ['simulation', ['#values', '#vibrationChannel']], ['maintenance', ['#storageStatus']]]) {
      await page.click('[data-view="'+view+'"]');
      if(view==='simulation')await page.locator('#developerPanel>summary').click();
      await page.locator('iframe').waitFor();
      const inner = page.frameLocator('iframe');
      if(view==='simulation'){
        await inner.locator('#developerOptions>summary').click();
        await inner.locator('#debugReadings>summary').click();
      }
      for (const selector of selectors) await inner.locator(selector).locator('xpath=ancestor-or-self::section[1]').waitFor({state: 'visible', timeout: 20000});
      if (view === 'history') {
        await inner.locator('#all').click();
        await inner.locator('#queryHistoryStats').click();
        await inner.locator('#historyStatistics').waitFor({state:'visible'});
      }
      if (view === 'persona') {
        await page.click('#preferencesTab');
        await page.frameLocator('iframe').locator('#feedbackSettings').waitFor({state:'visible'});
        await page.click('#personaTab');
        await page.frameLocator('iframe').locator('#persona').waitFor({state:'visible'});
      }
    }
    await page.click('[data-view="mcp"]');
    if (!(await page.locator('#tunnelId').isVisible())) throw Error('Secure form missing after navigation');
    await page.click('[data-view="overview"]');
    await page.screenshot({path: path.join(output, 'overview-desktop.png'), fullPage: true});
    await page.click('[data-view="setup"]');
    await page.click('[data-step="1"]');
    await page.screenshot({path: path.join(output, 'setup-pairing.png'), fullPage: true});
    for (const viewport of [{width:768,height:1024}, {width:390,height:844}]) {
      await page.setViewportSize(viewport);
      await page.click('[data-view="overview"]');
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1)) throw Error('Page overflow '+viewport.width);
      await page.screenshot({path:path.join(output,'overview-'+viewport.width+'.png'),fullPage:true});
    }
    if (errors.length) throw Error(errors.join('\n'));
    if (failures.length) throw Error(failures.join('\n'));
    fs.writeFileSync(path.join(output,'browser-report.json'), JSON.stringify({passed:true, views:10, wizard_steps:4, responsive:[1360,768,390], local_config_generated:true, errors},null,2));
    console.log('PASS: wizard, config generation, existing control pages, offline history, preferences navigation, desktop/tablet/mobile; no browser errors');
  } finally { await browser.close(); }
})().catch(e => {console.error(e); process.exitCode=1;});
