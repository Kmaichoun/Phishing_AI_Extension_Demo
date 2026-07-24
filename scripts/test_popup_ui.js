'use strict';

const fs = require('fs');
const path = require('path');

const projectRoot = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(projectRoot, 'popup.html'), 'utf8');
const css = fs.readFileSync(path.join(projectRoot, 'popup.css'), 'utf8');
const script = fs.readFileSync(path.join(projectRoot, 'popup.js'), 'utf8');

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
