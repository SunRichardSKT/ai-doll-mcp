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
  const state = {ports: [{port: 'COM4', description: 'fixture'}], selected_port: 'COM4',
    firmware: 'fixture-version', running: false, report: null};
  const requests = [];
  const context = vm.createContext({
    document: {getElementById: get, querySelectorAll: () => [{}, {}, {}, {}]},
    Option: function(text, value) {this.text = text; this.value = value;}, TextEncoder,
    setInterval() {},
    fetch: async (url, options) => {
      if (url === '/api/start') requests.push(JSON.parse(options.body));
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
  console.log('Flash page: custom/random names, UTF-8 limit, request payload and hotspot display passed.');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
