'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');

const projectRoot = path.resolve(__dirname, '..');
const extensionRoot = path.join(projectRoot, 'extension');
const html = fs.readFileSync(path.join(extensionRoot, 'popup.html'), 'utf8');
const css = fs.readFileSync(path.join(extensionRoot, 'popup.css'), 'utf8');
const script = fs.readFileSync(path.join(extensionRoot, 'popup.js'), 'utf8');

const htmlIds = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
const requiredIds = new Set([
  ...[...script.matchAll(/\$\('([^']+)'\)/g)].map(match => match[1]),
  'manualDomain',
  'manualScore',
  'manualThreat',
  'manualSummary',
  'manualReasons',
]);

for (const id of requiredIds) {
  if (!htmlIds.has(id)) {
    throw new Error(`Popup element is missing: #${id}`);
  }
}

for (const expected of [
  'class="mode-list"',
  'class="tools-panel"',
  'class="manual-result"',
  'class="settings-list"',
  'id="pageScanningEnabled"',
  'id="privacyMode"',
  'id="llmEnabled"',
  'id="riskyAdProtection"',
  'id="adFilterMode"',
  'id="adFilterSiteException"',
  'id="popupThemeToggle"',
  'id="openWebApp" class="header-action login-entry"',
  'class="theme-icon theme-icon-sun"',
  'class="theme-icon theme-icon-moon"',
]) {
  if (!html.includes(expected)) {
    throw new Error(`Popup structure is missing: ${expected}`);
  }
}

if (html.includes('popupCommandPalette')) {
  throw new Error('Legacy command palette remains in the compact popup.');
}

if (!script.includes('function isInjectablePageUrl(value)')) {
  throw new Error('Popup must reject restricted page protocols before script injection.');
}

if (script.includes("console.warn('Phish Radar injection failed:")) {
  throw new Error('Expected browser injection failures must not pollute Extension Errors.');
}

if (/id="openWebApp"[^>]*\bhidden\b/.test(html)) {
  throw new Error('The Login entry must be visible in the Popup header.');
}

if (/\p{Extended_Pictographic}/u.test(`${html}\n${script}`)) {
  throw new Error('Popup icons must use SVG or CSS shapes, not Emoji.');
}

if (css.includes('#22ad89') || css.includes('#2bc19b')) {
  throw new Error('The retired emerald action palette remains in the Popup.');
}

const outerViewportRule = css.match(/html,\s*body\s*\{([\s\S]*?)\}/);
if (!outerViewportRule || !/overflow:\s*hidden/.test(outerViewportRule[1])) {
  throw new Error('The outer Popup viewport must not create a second scrollbar.');
}

const appScrollRule = css.match(/body\[data-surface="popup"\]\s+\.app\s*\{([\s\S]*?)\}/);
if (!appScrollRule || !/height:\s*100%/.test(appScrollRule[1]) || !/overflow-y:\s*auto/.test(appScrollRule[1])) {
  throw new Error('The Popup app must be the only vertical scroll container.');
}

function cssVariable(name) {
  const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-f]{6})`, 'i'));
  if (!match) throw new Error(`CSS variable not found: ${name}`);
  return match[1];
}

function themeVariables(block) {
  return Object.fromEntries(
    [...block.matchAll(/(--popup-[\w-]+):\s*(#[0-9a-f]{6})/gi)]
      .map(match => [match[1], match[2]]),
  );
}

function luminance(hex) {
  const channels = hex.slice(1).match(/.{2}/g).map(value => {
    const channel = Number.parseInt(value, 16) / 255;
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(first, second) {
  const light = Math.max(luminance(first), luminance(second));
  const dark = Math.min(luminance(first), luminance(second));
  return (light + 0.05) / (dark + 0.05);
}

for (const [foreground, background, label] of [
  ['--popup-text', '--popup-bg', 'main text'],
  ['--popup-muted', '--popup-bg', 'muted text'],
  ['--popup-text', '--popup-surface', 'surface text'],
]) {
  const ratio = contrast(cssVariable(foreground), cssVariable(background));
  if (ratio < 4.5) {
    throw new Error(`${label} contrast is ${ratio.toFixed(2)}:1; expected at least 4.5:1`);
  }
}

const darkVariables = themeVariables(css.match(/:root\s*\{([\s\S]*?)\}/)?.[1] || '');
const lightVariables = themeVariables(
  css.match(/html\.phish-radar-theme-light\s*\{([\s\S]*?)\}/)?.[1] || '',
);

for (const [theme, variables] of [['dark', darkVariables], ['light', lightVariables]]) {
  for (const name of ['--popup-text', '--popup-muted', '--popup-bg', '--popup-surface', '--popup-accent', '--popup-button-ink']) {
    if (!variables[name]) throw new Error(`${theme} theme variable is missing: ${name}`);
  }
  for (const [foreground, background, label] of [
    ['--popup-text', '--popup-bg', 'main text'],
    ['--popup-muted', '--popup-bg', 'muted text'],
    ['--popup-text', '--popup-surface', 'surface text'],
    ['--popup-button-ink', '--popup-accent', 'primary button'],
  ]) {
    const ratio = contrast(variables[foreground], variables[background]);
    if (ratio < 4.5) {
      throw new Error(`${theme} ${label} contrast is ${ratio.toFixed(2)}:1; expected at least 4.5:1`);
    }
  }
}

console.log(`Popup UI contract passed (${requiredIds.size} functional IDs, SVG/CSS icons, and light/dark contrast).`);

async function testAdFilterControls() {
  const saved = { privacyMode: true, llmEnabled: true, pageScanningEnabled: false, threshold: 75, adFilterAllowlist: ['other.example'] };
  const broadcasts = [];
  let backgroundListener;
  const event = () => ({ addListener() {} });
  const backgroundContext = vm.createContext({
    URL, console, importScripts() {},
    chrome: {
      runtime: {
        onInstalled: event(),
        onMessage: { addListener(listener) { backgroundListener = listener; } },
      },
      storage: {
        sync: {
          async get(defaults) { return { ...defaults, ...saved }; },
          async set(value) { Object.assign(saved, value); },
        },
        session: { async get() { return {}; }, async set() {}, async remove() {} },
      },
      tabs: {
        onUpdated: event(), onActivated: event(), onCreated: event(), onRemoved: event(),
        async query() { return [{ id: 1, url: 'https://www.up-manga.com/genres/manhwa/' }, { id: 2, url: 'chrome://extensions' }]; },
        async sendMessage(tabId, message) { broadcasts.push({ tabId, message }); },
      },
      webNavigation: { onBeforeNavigate: event(), onCreatedNavigationTarget: event(), onCommitted: event() },
    },
  });
  vm.runInContext(fs.readFileSync(path.join(extensionRoot, 'background.js'), 'utf8'), backgroundContext);
  const backgroundMessage = message => new Promise(resolve => backgroundListener(message, {}, resolve));

  const defaults = await backgroundMessage({ type: 'GET_SETTINGS' });
  assert.equal(defaults.settings.riskyAdProtection, true, 'New protection must default on without resetting existing settings.');
  assert.equal(defaults.settings.adFilterMode, 'all', 'All detected ads is the default for existing installations.');
  assert.equal(defaults.settings.privacyMode, true);
  assert.equal(defaults.settings.pageScanningEnabled, false);
  await backgroundMessage({ type: 'SET_SETTINGS', settings: { riskyAdProtection: false } });
  assert.equal(saved.riskyAdProtection, false);
  assert.equal(saved.privacyMode, true);
  assert.equal(saved.llmEnabled, true);
  assert.equal(saved.threshold, 75);
  assert.equal(saved.pageScanningEnabled, false);
  assert.equal(broadcasts.length, 1, 'Filter settings must reach normal pages even while page scanning is paused.');
  assert.equal(broadcasts[0].message.type, 'SETTINGS_UPDATED');
  assert.equal(broadcasts[0].message.settings.privacyMode, true);

  const broadcastCount = broadcasts.length;
  await backgroundMessage({ type: 'SET_SETTINGS', settings: { adFilterMode: 'risky' } });
  assert.equal(saved.adFilterMode, 'risky', 'Risk-only mode must be stored explicitly.');
  assert.equal(broadcasts.length, broadcastCount + 1, 'Changing only the mode must reach current pages.');
  assert.equal(broadcasts.at(-1).message.settings.adFilterMode, 'risky');
  assert.equal(saved.privacyMode, true);
  assert.equal(saved.llmEnabled, true);
  assert.equal(saved.pageScanningEnabled, false);
  assert.equal(saved.threshold, 75);
  await backgroundMessage({ type: 'SET_SETTINGS', settings: { adFilterMode: 'invalid-mode' } });
  assert.equal(saved.adFilterMode, 'all', 'Unknown modes normalize to all detected ads.');
  saved.adFilterMode = 'RISKY';
  assert.equal((await backgroundMessage({ type: 'GET_SETTINGS' })).settings.adFilterMode, 'all', 'Reading storage also normalizes unexpected mode values.');
  saved.adFilterMode = 'all';

  await backgroundMessage({ type: 'SET_SETTINGS', settings: {
    adFilterAllowlist: [' WWW.UP-MANGA.COM. ', 'www.up-manga.com', 'sub.up-manga.com', '*.up-manga.com', 'foo..bar', 'evil.example/path', 'https://evil.example', 'bad@evil.example'],
  } });
  assert.deepEqual([...saved.adFilterAllowlist], ['www.up-manga.com', 'sub.up-manga.com'], 'Exceptions must remain exact hostnames and reject paths or wildcards.');

  const elements = new Map([...htmlIds].map(id => [id, {
    checked: false, disabled: false, textContent: '', value: '', events: {}, style: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(type, handler) { this.events[type] = handler; },
    setAttribute() {},
  }]));
  const popupMessages = [];
  const popupContext = vm.createContext({
    URL, console,
    document: { getElementById(id) { return elements.get(id); } },
    chrome: {
      runtime: { sendMessage(message, callback) { popupMessages.push(message); backgroundMessage(message).then(callback); } },
      storage: { onChanged: event() },
      tabs: {
        async get() { return { url: 'https://www.up-manga.com/genres/manhwa/' }; },
        sendMessage(tabId, message, callback) {
          callback(message.type === 'GET_AD_FILTER_STATS' ? { ok: true, stats: { hiddenCount: 7, blockedClicks: 2 } } : { ok: true });
        },
      },
    },
    PhishRadarAppTrust: require(path.join(extensionRoot, 'app-trust.js')),
  });
  vm.runInContext(script.replace(/\bload\(\);\s*$/, ''), popupContext);
  vm.runInContext("activeTab = { id: 1, url: 'https://WWW.UP-MANGA.COM/genres/manhwa/' }; renderAdFilter({riskyAdProtection:true, adFilterAllowlist:[]});", popupContext);
  assert.equal(vm.runInContext('currentAdFilterHost()', popupContext), 'www.up-manga.com');
  assert.equal(elements.get('adFilterSiteException').disabled, false);
  assert.equal(elements.get('adFilterMode').value, 'all');
  assert.equal(elements.get('adFilterMode').disabled, false);

  saved.adFilterAllowlist = ['other.example'];
  elements.get('adFilterSiteException').checked = true;
  await elements.get('adFilterSiteException').events.change({ target: elements.get('adFilterSiteException') });
  assert.deepEqual([...saved.adFilterAllowlist], ['www.up-manga.com', 'other.example'], 'Adding one site must preserve other exceptions.');
  assert.equal(saved.privacyMode, true);
  assert.equal(saved.llmEnabled, true);
  assert.equal(saved.pageScanningEnabled, false);
  assert.equal(saved.threshold, 75);
  assert.deepEqual(Object.keys(popupMessages.find(message => message.type === 'SET_SETTINGS').settings), ['adFilterAllowlist']);

  elements.get('adFilterSiteException').checked = false;
  await elements.get('adFilterSiteException').events.change({ target: elements.get('adFilterSiteException') });
  assert.deepEqual([...saved.adFilterAllowlist], ['other.example']);
  elements.get('riskyAdProtection').checked = true;
  await elements.get('riskyAdProtection').events.change({ target: elements.get('riskyAdProtection') });
  assert.equal(saved.riskyAdProtection, true);
  assert.match(elements.get('adFilterStatus').textContent, /7.*2/, 'Popup must display the independent filter counts.');
  assert.match(elements.get('adFilterStatus').textContent, /ซ่อนโฆษณา/, 'Hidden ad counts must not claim phishing evidence.');

  const sentBeforeModeChange = popupMessages.length;
  elements.get('adFilterMode').value = 'risky';
  await elements.get('adFilterMode').events.change({ target: elements.get('adFilterMode') });
  assert.equal(saved.adFilterMode, 'risky');
  assert.equal(elements.get('adFilterMode').value, 'risky');
  assert.deepEqual(Object.keys(popupMessages.slice(sentBeforeModeChange).find(message => message.type === 'SET_SETTINGS').settings), ['adFilterMode'], 'Mode changes save only their own preference.');
  assert.deepEqual([...saved.adFilterAllowlist], ['other.example']);
  assert.equal(saved.threshold, 75);
  assert.equal(saved.privacyMode, true);
  assert.equal(saved.llmEnabled, true);
  assert.equal(saved.pageScanningEnabled, false);
  elements.get('adFilterMode').value = 'all';
  await elements.get('adFilterMode').events.change({ target: elements.get('adFilterMode') });
  assert.equal(saved.adFilterMode, 'all');
  vm.runInContext('renderAdFilter({riskyAdProtection:false, adFilterMode:"risky", adFilterAllowlist:[]});', popupContext);
  assert.equal(elements.get('adFilterMode').value, 'risky', 'Disabling does not discard the selected mode.');
  assert.equal(elements.get('adFilterMode').disabled, true);
  vm.runInContext('renderAdFilter({riskyAdProtection:true, adFilterMode:"unexpected", adFilterAllowlist:[]});', popupContext);
  assert.equal(elements.get('adFilterMode').value, 'all');

  vm.runInContext("activeTab.url = 'chrome://extensions'; renderAdFilter();", popupContext);
  assert.equal(elements.get('adFilterSiteException').disabled, true);
  vm.runInContext("activeTab.url = PhishRadarAppTrust.DEFAULT_WEB_APP_URL; renderAdFilter();", popupContext);
  assert.equal(elements.get('adFilterSiteException').disabled, true, 'Phish Radar origin exception is managed by the system.');
  assert.match(elements.get('adFilterStatus').textContent, /Phish Radar/);
  console.log('Ad-filter controls passed (all/risky mode selection and normalization, independent toggle, exact host exceptions, preference preservation and live status).');
}

testAdFilterControls().catch(error => { console.error(error); process.exitCode = 1; });
