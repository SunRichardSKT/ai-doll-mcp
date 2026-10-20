// Usage: NODE_PATH=<your node_modules> node capture_preview.cjs
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const out=path.join(__dirname,'output');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const errors=[],images=[];
 try{
  const page=await browser.newPage({viewport:{width:1460,height:1190},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(pathToFileURL(path.join(out,'preview.html')).href);
  await page.waitForFunction(()=>window.modelReady===true);
  for(const [mode,name] of [['exploded','preview.png'],['assembled','assembled.png'],['tray','tray.png'],['lid',null]]){
   await page.locator(`[data-mode=${mode}]`).click();
   if(name){await page.locator('canvas').screenshot({path:path.join(out,name)});images.push(name);}
  }
  await page.locator('[data-mode=base]').click();
  await page.locator('#side').click();await page.locator('#cut').click();
  await page.locator('canvas').screenshot({path:path.join(out,'side.png')});images.push('side.png');
  await page.locator('#cut').click();
  await page.locator('[data-mode=exploded]').click();await page.locator('#reset').click();
  await page.setViewportSize({width:390,height:900});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  // The original desktop viewer used a 600px minimum. Stacked viewer must fit phones.
  if(overflow)throw Error('Mobile preview overflows viewport');
  await page.goto(pathToFileURL(path.join(out,'stack.svg')).href);
  await page.setViewportSize({width:1040,height:650});
  await page.screenshot({path:path.join(out,'stack.png')});images.push('stack.png');
  if(errors.length)throw Error(errors.join('\n'));
  const report={passed:true,modes:['exploded','assembled','base','tray','lid'],mobile390:true,
    javascriptErrors:errors,images,geometrySource:'meshes.json exported from actual STEP solids'};
  fs.writeFileSync(path.join(out,'preview_check.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
