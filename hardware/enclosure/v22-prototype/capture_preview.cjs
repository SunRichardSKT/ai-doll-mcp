/* Optional PNG refresh. Install Playwright separately; the HTML viewer needs no runtime. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

(async () => {
  const out = path.join(__dirname, 'output');
  const browser = await chromium.launch({
    channel: process.env.CHROME_CHANNEL || 'msedge', headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1230 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(pathToFileURL(path.join(out, 'preview.html')).href);
    await page.waitForFunction(() => window.modelReady === true);
    await page.screenshot({ path: path.join(out, 'preview.png'), fullPage: true });
    await page.locator('[data-mode=assembled]').click();
    await page.screenshot({ path: path.join(out, 'assembled.png'), fullPage: true });
    await page.locator('[data-mode=base]').click();
    await page.locator('#cut').click();
    await page.screenshot({ path: path.join(out, 'cutaway.png'), fullPage: true });
    await page.locator('#cut').click();
    await page.locator('[data-mode=lid]').click();
    await page.screenshot({ path: path.join(out, 'lid.png'), fullPage: true });
    const report = { revision: 'V22-ENC-P02', date: '2026-10-20', javascriptErrors: errors,
      modesChecked: 4, pngFiles: ['preview.png', 'assembled.png', 'cutaway.png', 'lid.png'] };
    fs.writeFileSync(path.join(out, 'export_check.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify(report));
    if (errors.length) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
