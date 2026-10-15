// Operit 1.12.2 returns the screen function itself during registration. Normal
// execution loads CommonJS exports. Accept both without dropping the path marker.
const screenModule = require('./ui/settings.ui.js');
const screen = typeof screenModule === 'function' ? screenModule : screenModule.default;
function registerToolPkg() {
  ToolPkg.registerToolboxUiModule({id:'settings', runtime:'compose_dsl', screen,
    title:'AI Doll · 连接与互动', params:{}});
  return true;
}
exports.registerToolPkg = registerToolPkg;
