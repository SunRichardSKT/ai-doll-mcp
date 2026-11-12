// Run the real page script against a small DOM and mocked HTTP; never access a board.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {TextEncoder} = require('node:util');

async function main() {
  const source = fs.readFileSync(path.join(__dirname, 'flash.html'), 'utf8');
  const elements = new Map([...source.matchAll(/id="([^"]+)"/g)].map(([, id]) => [id, {
    value: '', textContent: '', hidden: false, checked: false, disabled: false, dataset: {},
    replaceChildren() {}, add() {}
  }]));
  const get = id => elements.get(id);
  get('mode').value = 'update';
  get('nameMode').value = 'random';
  get('firmwareSource').value = 'bundled';
  const state = {ports: [{port: 'COM4', description: 'fixture'}], selected_port: 'COM4',
    firmware: 'fixture-version', running: false, report: null,
    source: {kind:'bundled',label:'随包固件',source_id:'bundled-hash'}};
  const requests = [], sourceRequests = [];
  const latest = {tag:'v9',asset_name:'AI_Doll_Firmware_v9.zip',release_url:'https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v9'};
  let importFailure = false;
  const context = vm.createContext({
    document: {getElementById: get, querySelectorAll: () => [{}, {}, {}, {}]},
    Option: function(text, value) {this.text = text; this.value = value;}, TextEncoder,
    setInterval() {}, Uint8Array,
    btoa: value => Buffer.from(value,'binary').toString('base64'),
    fetch: async (url, options) => {
      if (url === '/api/start') requests.push(JSON.parse(options.body));
      if (url.startsWith('/api/firmware/')||url==='/api/releases/latest') {
        sourceRequests.push({url,options});
        if (url==='/api/releases/latest') state.latest=latest;
        if (url==='/api/firmware/local') {
          if (importFailure) return {ok:false,json:async()=>({error:'固件 SHA-256 校验失败'})};
          state.source={kind:'local',label:'本地固件',source_id:'local-hash'};
        }
        if (url==='/api/firmware/release') state.source={kind:'github',label:'GitHub · v9',source_id:'github-hash'};
        if (url==='/api/firmware/bundled') state.source={kind:'bundled',label:'随包固件',source_id:'bundled-hash'};
        return {ok:true,json:async()=>url==='/api/releases/latest'?latest:state.source};
      }
      return {ok: true, json: async () => url === '/api/start' ? {started: true} : state};
    }
  });
  vm.runInContext(source.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(get('start').disabled, false);
  get('nameMode').value = 'custom'; get('nameMode').onchange();
  assert.equal(get('customNameField').hidden, false);
  assert.equal(get('start').disabled, true);
  get('customName').value = '樱'.repeat(11); get('customName').oninput();
  assert.equal(get('start').disabled, true);
  assert.match(get('nameHint').textContent, /32/);
  get('customName').value = '  小樱  '; get('customName').oninput();
  assert.equal(get('start').disabled, false);
  await get('start').onclick();
  assert.equal(requests[0].name, '小樱');
  assert.equal(requests[0].factory, false);
  get('nameMode').value = 'random'; get('nameMode').onchange();
  await get('start').onclick();
  assert.equal(requests[1].name, null);
  state.report = {status: 'success', device_id: 'AI-Doll-fixture', configuration_hotspot: '小樱'};
  await get('refresh').onclick();
  assert.equal(get('deviceName').textContent, '小樱');
  assert.equal(get('successDetails').hidden, false);
  assert.match(source,/href="http:\/\/192\.168\.4\.1\/setup"/);
  const flashCount=requests.length;
  get('firmwareSource').value='local';get('firmwareSource').onchange();
  assert.equal(get('start').disabled,true,'unimported selection cannot flash the previous source');
  const file={name:'fixture.zip',size:400};get('firmwareFiles').files=[file];
  await get('firmwareFiles').onchange();
  assert.equal(sourceRequests.at(-1).options.body,file);
  assert.equal(sourceRequests.at(-1).options.headers['Content-Type'],'application/zip');
  assert.equal(get('start').disabled,false);
  importFailure=true;
  await get('firmwareFiles').onchange();
  assert.match(get('sourceError').textContent,/SHA-256/);
  assert.equal(state.source.source_id,'local-hash');
  importFailure=false;
  const names=['FLASH_MANIFEST.json','bootloader.bin','partitions.bin','boot_app0.bin','firmware.bin'];
  get('firmwareFiles').files=names.map(name=>({name,size:1,arrayBuffer:async()=>new Uint8Array([1]).buffer}));
  await get('firmwareFiles').onchange();
  assert.equal(JSON.parse(sourceRequests.at(-1).options.body).files.length,5);
  assert.equal(requests.length,flashCount,'file imports never start USB flashing');
  get('firmwareSource').value='github';get('firmwareSource').onchange();
  await get('checkLatest').onclick();
  assert.equal(get('start').disabled,true,'querying a release does not select or flash it');
  assert.match(get('latestInfo').textContent,/v9/);
  await get('useLatest').onclick();
  assert.equal(get('start').disabled,false);
  assert.equal(requests.length,flashCount);
  await get('start').onclick();
  assert.equal(requests.at(-1).source_id,'github-hash');
  state.preparing=true;await get('refresh').onclick();
  assert.equal(get('start').disabled,true);
  assert.equal(get('firmwareFiles').disabled,true);
  state.preparing=false;await get('refresh').onclick();
  get('firmwareSource').value='bundled';await get('firmwareSource').onchange();
  assert.equal(state.source.kind,'bundled');
  console.log('Flash page: names, setup link, ZIP/five-file selection, Release selection, errors and busy state passed.');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
