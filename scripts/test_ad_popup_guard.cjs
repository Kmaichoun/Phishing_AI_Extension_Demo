// Exercise the actual background worker with controlled Chrome navigation events.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const extension = path.resolve(__dirname, '../extension');
const sourceUrl = 'https://www.up-manga.com/genres/manhwa/';
const popupUrl = 'https://casino.example/claim-bonus';
const tick = () => new Promise(resolve => setImmediate(resolve));

function worker(options = {}) {
  const settings = { riskyAdProtection: true, adFilterAllowlist: [], ...options.settings };
  const tabs = new Map([
    [1, { id: 1, url: options.sourceUrl || sourceUrl }],
    [2, { id: 2, url: options.popupUrl || popupUrl }]
  ]);
  const listeners = new Map();
  const messages = [];
  const removed = [];
  const updates = [];
  const fetches = [];
  const event = name => ({ addListener(callback) { listeners.set(name, callback); } });
  let context;
  const chrome = {
    runtime: { onInstalled: event('installed'), onMessage: event('message'),
      getURL: value => 'chrome-extension://test/' + value },
    action: { setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {}, setTitle: async () => {} },
    scripting: { insertCSS: async () => {}, executeScript: async () => {} },
    storage: {
      sync: { get: async defaults => ({ ...(typeof defaults === 'object' ? defaults : {}), ...settings }),
        set: async next => Object.assign(settings, next) },
      session: { get: async () => ({}), set: async () => {}, remove: async () => {} },
      local: { get: async defaults => defaults || {}, set: async () => {} }
    },
    tabs: {
      onUpdated: event('updated'), onActivated: event('activated'), onRemoved: event('removed'),
      query: async () => [...tabs.values()],
      get: async id => {
        if (!tabs.has(id)) throw new Error('No tab');
        return { ...tabs.get(id) };
      },
      update: async (id, details) => { updates.push({ id, ...details }); return details; },
      create: async details => details,
      remove: async id => {
        if (options.removeError) throw new Error('Tab cannot be closed');
        removed.push(id); tabs.delete(id);
      },
      sendMessage: async (id, message, frameOptions) => {
        messages.push({ id, message, options: frameOptions });
        if (message.type === 'CHECK_AD_FILTER_TARGET') {
          if (options.messageError) throw new Error('Receiving end does not exist');
          if (options.beforeResponse) await options.beforeResponse({ settings, tabs });
          return Object.hasOwn(options, 'response') ? options.response : {
            ok: true, blocked: true, pageUrl: tabs.get(1)?.url,
            targetUrl: message.targetUrl, reasons: ['Verified risky ad destination']
          };
        }
        return { ok: true };
      }
    },
    webNavigation: {
      onCreatedNavigationTarget: event('created'), onBeforeNavigate: event('before'),
      onCommitted: event('committed'), onCompleted: event('completed'),
      getFrame: async ({ tabId }) => ({ url: tabs.get(tabId)?.url, frameId: 0 })
    }
  };
  context = vm.createContext({ console, URL, URLSearchParams, Map, Set, AbortController,
    setTimeout, clearTimeout, chrome,
    fetch: async (...args) => { fetches.push(args); throw new Error('No network expected'); },
    importScripts: (...files) => {
      for (const file of files) vm.runInContext(fs.readFileSync(path.join(extension, file), 'utf8'), context, { filename: file });
    }
  });
  vm.runInContext(fs.readFileSync(path.join(extension, 'background.js'), 'utf8'), context, { filename: 'background.js' });
  return {
    settings, tabs, listeners, messages, removed, updates, fetches,
    async popup(details = {}) {
      assert.ok(listeners.has('created'), 'background must register a popup-created listener');
      await listeners.get('created')({ sourceTabId: 1, sourceFrameId: 0, tabId: 2,
        url: options.popupUrl || popupUrl, timeStamp: Date.now(), ...details });
      await tick(); await tick();
    },
    async request(message) {
      return new Promise(resolve => listeners.get('message')(message, {}, resolve));
    }
  };
}

async function remainsOpen(label, options, details) {
  const w = worker(options);
  await w.popup(details);
  assert.deepEqual(w.removed, [], label);
  assert.equal(w.fetches.length, 0, label + ': filtering must not call RF/LLM/backend');
  return w;
}

(async () => {
  const confirmed = worker();
  await confirmed.popup();
  assert.deepEqual(confirmed.removed, [2], 'only the newly opened confirmed ad tab is closed');
  assert.equal(confirmed.tabs.has(1), true, 'the source reading page remains open');
  const query = confirmed.messages.find(entry => entry.message.type === 'CHECK_AD_FILTER_TARGET');
  assert.ok(query, 'the actual source DOM runtime must corroborate the popup destination');
  assert.equal(query.id, 1);
  assert.equal(query.message.targetUrl, popupUrl);
  assert.equal(query.options?.frameId, 0, 'popup destination is checked by the top-frame runtime');
  assert.ok(confirmed.messages.some(entry => entry.message.type === 'AD_FILTER_POPUP_BLOCKED'), 'successful closure updates the source counter');
  assert.equal(confirmed.fetches.length, 0, 'popup filtering never changes or requests URL Risk Model scoring');

  await remainsOpen('protection switched off', { settings: { riskyAdProtection: false } });
  await remainsOpen('exact hostname exception', { settings: { adFilterAllowlist: ['www.up-manga.com'] } });
  const otherSubdomain = worker({ settings: { adFilterAllowlist: ['up-manga.com'] } });
  await otherSubdomain.popup();
  assert.deepEqual(otherSubdomain.removed, [2], 'an exception for apex does not exempt www');
  await remainsOpen('trusted Phish Radar source', { sourceUrl: 'https://phish-radar.taila97307.ts.net/#/login' });
  await remainsOpen('trusted Phish Radar destination', { popupUrl: 'https://phish-radar.taila97307.ts.net/#/login' });
  await remainsOpen('same first-party destination', { popupUrl: 'https://www.up-manga.com/reader/chapter-1/' });
  await remainsOpen('reviewed site apex alias', { popupUrl: 'https://up-manga.com/reader/chapter-1/' });
  for (const loginHost of ['accounts.google.com', 'login.microsoftonline.com', 'login.live.com', 'appleid.apple.com']) {
    await remainsOpen('official login destination ' + loginHost, { popupUrl: 'https://' + loginHost + '/oauth/authorize?client_id=test' });
  }
  await remainsOpen('non-HTTP destination', { popupUrl: 'chrome-extension://test/popup.html' });
  await remainsOpen('no DOM receiver', { messageError: true });
  await remainsOpen('undefined DOM response', { response: undefined });
  await remainsOpen('runtime rejects target', { response: { ok: true, blocked: false } });
  await remainsOpen('runtime did not report success', { response: { ok: false, blocked: true } });
  await remainsOpen('string blocked flag is not proof', { response: { ok: true, blocked: 'true' } });
  await remainsOpen('runtime response came from another page', { response: { ok: true, blocked: true, pageUrl: 'https://other.example/' } });
  await remainsOpen('runtime response missing source identity', { response: { ok: true, blocked: true } });
  await remainsOpen('closed source tab', { beforeResponse: ({ tabs }) => tabs.delete(1) });
  await remainsOpen('source page changed while checked', { beforeResponse: ({ tabs }) => tabs.set(1, { id: 1, url: 'https://www.up-manga.com/reader/new/' }) });
  await remainsOpen('popup navigated elsewhere while checked', { beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: 'https://legitimate.example/login' }) });
  await remainsOpen('protection disabled while checked', { beforeResponse: ({ settings }) => { settings.riskyAdProtection = false; } });
  await remainsOpen('source excepted while checked', { beforeResponse: ({ settings }) => { settings.adFilterAllowlist = ['www.up-manga.com']; } });
  await remainsOpen('cannot close same source tab', {}, { tabId: 1 });
  await remainsOpen('iframe popup cannot impersonate the top frame', {}, { sourceFrameId: 7 });
  await remainsOpen('about:blank navigation event has no known destination', { popupUrl: 'about:blank' });
  const blankTarget = worker({ beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: 'about:blank' }) });
  await blankTarget.popup();
  assert.deepEqual(blankTarget.removed, [2], 'an exact verified event destination may be closed before its new tab leaves about:blank');
  const matchingWarning = worker({ beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: 'chrome-extension://test/warning.html?target=' + encodeURIComponent(popupUrl) }) });
  await matchingWarning.popup();
  assert.deepEqual(matchingWarning.removed, [2], 'RF warning race for the same verified destination can close the popup');
  await remainsOpen('RF warning race for a different destination', { beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: 'chrome-extension://test/warning.html?target=' + encodeURIComponent('https://other.example/') }) });
  const pending = worker({ beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: 'about:blank', pendingUrl: popupUrl }) });
  await pending.popup();
  assert.deepEqual(pending.removed, [2], 'verified pending navigation is handled');
  await remainsOpen('unrelated pending navigation takes priority over old tab URL', { beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: popupUrl, pendingUrl: 'https://other.example/' }) });
  const hashOnly = worker({ beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: popupUrl + '#offer' }) });
  await hashOnly.popup();
  assert.deepEqual(hashOnly.removed, [2], 'hash changes do not change the verified network destination');
  await remainsOpen('query parameters are not discarded', { beforeResponse: ({ tabs }) => tabs.set(2, { id: 2, url: popupUrl + '?different=1' }) });
  const removeFailure = await remainsOpen('Chrome denies removal', { removeError: true });
  assert.ok(!removeFailure.messages.some(entry => entry.message.type === 'AD_FILTER_POPUP_BLOCKED'), 'failed removal must not increment blocked popup count');

  const defaults = worker();
  const settingsResponse = await defaults.request({ type: 'GET_SETTINGS' });
  assert.equal(settingsResponse.settings.threshold, 60, 'existing URL warning threshold remains unchanged');
  assert.equal(settingsResponse.settings.riskyAdProtection, true);
  const saved = await defaults.request({ type: 'SET_SETTINGS', settings: { riskyAdProtection: false, adFilterAllowlist: ['WWW.UP-MANGA.COM', 'www.up-manga.com', 'https://bad.example/'] } });
  assert.deepEqual(Array.from(saved.settings.adFilterAllowlist), ['www.up-manga.com']);
  assert.equal(saved.settings.threshold, 60);
  assert.ok(defaults.messages.some(entry => entry.message.type === 'SETTINGS_UPDATED'), 'current pages receive filtering settings immediately');
  console.log('Ad popup guard: confirmed popup, exceptions, first-party/login, errors, races, and settings regressions passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
