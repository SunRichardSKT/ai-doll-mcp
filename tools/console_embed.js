/* Reuse existing controls inside the management center, without a second implementation. */
(() => {
  const panel = new URLSearchParams(location.search).get('panel');
  if (!panel) return;
  if (panel === 'wifi') return;
  const style = document.createElement('style');
  style.textContent = 'body{max-width:none;margin:0;padding:0 3px;background:#f3f1e9;font-family:"Segoe UI","Microsoft YaHei",sans-serif}body>h1,body>p:not(#error){display:none}body>section{display:none;margin:0 0 16px;padding:22px;border:1px solid #d9dfd4;background:#fffefa;border-radius:14px}body>section.console-visible{display:block}#error:empty{display:none}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #2b6249;outline-offset:3px}';
  document.head.append(style);
  const selectors = {
    channels: ['#parts', '#sensorExperience'],
    simulation: ['#values', '#vibrationChannel'],
    persona: ['#persona'], preferences: ['#feedbackSettings'],
    history: ['#history', '#historyManagement'], maintenance: ['#storageStatus']
  };
  function show() {
    for (const selector of selectors[panel] || []) document.querySelector(selector)?.closest('section')?.classList.add('console-visible');
  }
  new MutationObserver(show).observe(document.body, {childList: true, subtree: true});
  show();
})();
