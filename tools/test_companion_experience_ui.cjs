const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHANNEL?{channel:process.env.PLAYWRIGHT_CHANNEL}:{})});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const css=require('node:fs').readFileSync(path.join(__dirname,'companion.html'),'utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
  await page.setContent('<html lang="zh-CN"><style>'+css+'</style><section>状态</section><section><div id="parts"></div></section></html>');
  await page.evaluate(()=>{
   window.calls=[];window.tool=async(name,args)=>{
    calls.push({name,args});
    if(name==='get_chat_context')return {preferences:{chat_integration_enabled:true,proactive_enabled:false},feedback:{tone:'自然',preferred_address:''},channels:[{channel:0,name:'头',aliases:['脑袋'],feedback_level:'normal',interaction_hint:''}]};
    return {updated:true};
   };
  });
  await page.addScriptTag({path:path.join(__dirname,'companion_experience.js')});
  await page.waitForSelector('[aria-label="CH0 部位名称"]');
  assert.equal(await page.isChecked('#chatIntegration'),true);assert.equal(await page.isChecked('#proactiveFeedback'),false);
  await page.fill('[aria-label="CH0 别名"]','脑袋、头顶');
  await page.selectOption('[aria-label="CH0 回应方式"]','light');
  await page.getByText('保存此部位',{exact:true}).click();
  let calls=await page.evaluate(()=>window.calls);
  let update=calls.find(c=>c.name==='update_body_part');assert.equal(update.args.changes.feedback_level,'light');assert.ok(!('name'in update.args.changes));
  assert.deepEqual(update.args.changes.aliases,['脑袋','头顶']);
  await page.fill('[aria-label="CH0 部位名称"]','头顶');await page.getByText('保存此部位',{exact:true}).click();
  await page.check('#proactiveFeedback');await page.click('#saveCompanionExperience');
  calls=await page.evaluate(()=>window.calls);assert.ok(calls.some(c=>c.name==='update_companion_preferences'&&c.args.changes.proactive_enabled));
  assert.ok(!calls.some(c=>['set_channel_config','set_sensor_config','set_input_enabled'].includes(c.name)));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  console.log('Presentation settings: partial rename, independent flags, no hardware reset PASS');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
