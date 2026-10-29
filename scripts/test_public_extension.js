const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../extension');
const requests = [];
const tabs = [];
let onMessage;
const event = { addListener() {} };
const context = vm.createContext({
  console, URL, setTimeout, clearTimeout,
  chrome: {
    runtime: { onInstalled: event, onMessage: { addListener(fn) { onMessage = fn; } } },
    tabs: { onUpdated: event, onActivated: event, async create(tab) { tabs.push(tab); } },
    webNavigation: { onBeforeNavigate: event }
  },
  async fetch(url) { requests.push(url); return { ok: true, async json() { return { ok: true }; } }; }
});
context.importScripts = (...files) => files.forEach(file => vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, { filename: file }));
context.importScripts('background.js');
(async () => {
  const result = await new Promise(resolve => onMessage({ type: 'OPEN_WEB_APP' }, {}, resolve));
  const origin = context.PhishRadarAppTrust.PUBLIC_WEB_APP_ORIGIN;
  assert.ok(origin.startsWith('https://'));
  assert.equal(result.ok, true);
  assert.equal(tabs[0].url, origin + '/#/login');
  await context.phishRadarPredictWithMl('https://example.com', 0);
  await context.phishRadarExplainWithLlm({ url: 'https://example.com' });
  await context.phishRadarSendFeedback({ url: 'https://example.com', user_label: 'safe' });
  assert.deepEqual(requests, ['/predict', '/explain', '/feedback'].map(p => origin + p));
  assert.equal(context.PhishRadarAppTrust.isTrustedWebAppUrl(origin + '/#/login'), true);
  assert.equal(context.PhishRadarAppTrust.isTrustedWebAppUrl('https://unrelated.trycloudflare.com'), false);
  console.log('Public extension passed: Login opens hosted web; ML, LLM and feedback use same hosted API.');
})().catch(error => { console.error(error); process.exitCode = 1; });
