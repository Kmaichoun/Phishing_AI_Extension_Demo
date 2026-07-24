'use strict';

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8');
const index = read('web-app/index.html');
const login = read('web-app/login.html');
const settings = read('web-app/settings.html');
const theme = read('web-app/theme.js');
const fonts = read('web-app/fonts.css');
const styles = read('web-app/professional-ui.css');
const awwwardsMotion = read('web-app/awwwards-motion.js');
const serviceWorker = read('web-app/sw.js');
const server = read('web-app/server.js');
const brandMark = read('web-app/assets/brand-mark.svg');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const functionalIds = [
  'privacyMode', 'backendStatus', 'accountSummary', 'accountAvatar', 'accountName',
  'accountRole', 'logoutButton', 'scan', 'scanForm', 'urlInput', 'scanButton',
  'formMessage', 'emptyResult', 'resultContent', 'riskLabel', 'resultTitle',
  'scoreRing', 'finalScore', 'ruleScore', 'mlScore', 'combinedScore', 'reasonList',
  'insightList', 'llmState', 'llmRiskType', 'llmExplanation', 'llmAdvice',
  'feedbackStatus', 'copyReport', 'openTarget', 'qr', 'qrVideo', 'qrCanvas',
  'qrPlaceholder', 'startCamera', 'stopCamera', 'qrFile', 'qrStatus', 'dashboard',
  'metricTotal', 'metricHigh', 'metricAverage', 'metricFeedback', 'exportCsv',
  'exportJson', 'copyDashboard', 'reportStatus', 'refreshHealth', 'healthBackend',
  'healthModel', 'healthLlm', 'healthFeedback', 'clearHistory', 'historyRows',
  'commandPalette', 'commandSearch', 'commandList'
];

for (const id of functionalIds) {
  assert(index.includes(`id="${id}"`), `Web App is missing functional element #${id}`);
}

const idMatches = Array.from(index.matchAll(/\sid="([^"]+)"/g), match => match[1]);
const duplicates = idMatches.filter((id, position) => idMatches.indexOf(id) !== position);
assert(duplicates.length === 0, `Duplicate IDs found: ${Array.from(new Set(duplicates)).join(', ')}`);

for (const page of [index, login, settings]) {
  assert(page.includes('professional-ui.css?v=20'), 'A Web App page is missing the professional UI layer');
  assert(page.includes('fonts.css?v=20'), 'A Web App page is missing the local font bundle');
  assert(page.includes('vendor/gsap.min.js?v=3.13.0'), 'A Web App page is missing pinned local GSAP');
  assert(page.includes('vendor/ScrollTrigger.min.js?v=3.13.0'), 'A Web App page is missing local ScrollTrigger');
  assert(page.includes('awwwards-motion.js?v=20'), 'A Web App page is missing the reference motion layer');
  assert(page.includes('theme-icon-sun') && page.includes('theme-icon-moon'), 'Theme toggle must use sun and moon SVG icons');
  assert(page.includes('assets/icon128.png?v=18'), 'A Web App page is missing the cache-safe fishing radar brand mark');
}

assert(index.includes('class="app-hero-title"'), 'Cinematic scanner hero is missing');
assert(index.includes('class="hero-title-line hero-title-accent"'), 'Editorial serif hero accent is missing');
assert(index.includes('ท่องเว็บไซต์อย่างปลอดภัยด้วย'), 'Requested safe browsing hero text is missing');
assert(index.includes('Phis radar AI'), 'Requested Phis radar AI hero line is missing');
assert(index.includes('data-motion-preloader'), 'Reference preloader markup is missing');
assert(!index.includes('hero-radar-ring'), 'Legacy outer radar rings are still present');
assert(styles.includes('.app-hero::before') && styles.includes('radial-gradient('), 'Hero background fade is missing');
assert(index.includes('id="scannerWorkbench"'), 'Scanner workbench anchor is missing');
assert(index.includes('class="scan-form hero-scan-form"'), 'URL form must live in the scanner hero');
assert(index.indexOf('id="scanForm"') < index.indexOf('id="scannerWorkbench"'), 'URL form must appear before scanner details');
assert(index.indexOf('id="previewHost"') < index.indexOf('id="resultContent"'), 'URL preview must appear before analysis details');
assert(!index.includes('data-brief-slide'), 'Removed Security Brief markup is still present');
assert(!index.includes('data-stack-card'), 'Removed evidence story markup is still present');
assert(!index.includes('professional-motion.js'), 'Removed professional motion script is still referenced');

assert(styles.includes('grid-template-columns: repeat(12, minmax(0, 1fr))'), 'The 12-column bento grid contract is missing');
assert(styles.includes('overflow-x: hidden'), 'Horizontal overflow protection is missing');
assert(styles.includes('@media (prefers-reduced-motion: reduce)'), 'Reduced-motion fallback is missing');
assert(styles.includes('.app-hero-title') && styles.includes('max-width: 90rem'), 'Hero width contract is missing');
assert(styles.includes('--display-font: "Outfit"'), 'Outfit is not the display font');
assert(styles.includes('--editorial-font: "Noto Serif Thai"'), 'Editorial serif font token is missing');
assert(fonts.includes('outfit-latin-400-700.woff2'), 'Local Outfit display font is missing');
assert(fonts.includes('ibm-plex-sans-thai-600.woff2'), 'Local Thai sans font is missing');
assert(fonts.includes('noto-serif-thai-500-600.woff2'), 'Local Thai serif accent font is missing');
assert(awwwardsMotion.includes("gsap.registerPlugin(ScrollTrigger)"), 'GSAP ScrollTrigger registration is missing');
assert(awwwardsMotion.includes("prefers-reduced-motion: reduce"), 'Reference motion reduced-motion guard is missing');
assert(awwwardsMotion.includes("reference: 'editorial-preloader-scroll-reveal'"), 'Reference motion contract is missing');
assert(awwwardsMotion.includes("clipPath: 'inset(0% 0 100% 0)'"), 'Preloader curtain reveal is missing');
assert(awwwardsMotion.includes("scrub: 1"), 'Hero scroll scrub is missing');
assert(!theme.includes('icon.textContent'), 'Theme script must not replace SVG icons with text');

const uiSource = [index, login, settings, theme].join('\n');
assert(!/\p{Extended_Pictographic}/u.test(uiSource), 'Web App UI source contains an emoji character');
assert(serviceWorker.includes("phish-radar-web-v20"), 'Service worker cache version was not upgraded');
assert(serviceWorker.includes('./professional-ui.css?v=20'), 'Professional CSS is missing from offline cache');
assert(serviceWorker.includes('./awwwards-motion.js?v=20'), 'Reference motion layer is missing from offline cache');
assert(serviceWorker.includes('./vendor/gsap.min.js?v=3.13.0'), 'Local GSAP is missing from offline cache');
assert(serviceWorker.includes('./fonts.css?v=20'), 'Local fonts are missing from offline cache');
assert(!serviceWorker.includes('professional-motion.js'), 'Removed professional motion script is still cached');
assert(serviceWorker.includes('./assets/icon128.png?v=18'), 'Brand mark PNG is missing from offline cache');
assert(server.includes("'.svg': 'image/svg+xml'"), 'Local Web App server must send the SVG MIME type');
assert(server.includes("'.woff2': 'font/woff2'"), 'Local Web App server must send the WOFF2 MIME type');
assert(brandMark.includes('Fishing rod and hook with a radar signal at the tip'), 'Brand mark description is missing');

console.log('Web App professional UI contract tests passed.');
