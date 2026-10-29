// Exercise the actual content-script helpers and click guard together with the
// shipped analyzer, without booting a browser or changing extension source.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const workspace = path.resolve(__dirname, '..');
const extension = path.join(workspace, 'extension');
const messages = [];
const redirectNotices = [];
const scanAnchors = [];
const scanBadges = [];
function classes(initial = []) {
  const values = new Set(initial);
  return {
    add(...names) { names.forEach(name => values.add(name)); },
    remove(...names) { names.forEach(name => values.delete(name)); },
    contains(name) { return values.has(name); },
    toggle(name, enabled) {
      if (enabled === undefined) enabled = !values.has(name);
      if (enabled) values.add(name); else values.delete(name);
      return enabled;
    }
  };
}
function node() {
  return {
    dataset: {}, classList: classes(), style: { setProperty() {}, removeProperty() {} },
    handlers: {}, removed: false,
    setAttribute() {}, removeAttribute() {},
    addEventListener(name) { this.handlers[name] = (this.handlers[name] || 0) + 1; },
    remove() { this.removed = true; }
  };
}
const location = new URL('https://www.facebook.com/');
const context = vm.createContext({
  console, URL, URLSearchParams, setTimeout, clearTimeout, location,
  __redirectNotices: redirectNotices,
  window: { addEventListener() {} },
  document: { body: {}, documentElement: {}, addEventListener() {},
    createElement: node,
    querySelectorAll(selector) {
      if (selector === 'a[href]') return scanAnchors;
      if (selector.includes('phish-radar-badge')) {
        const requestedId = selector.match(/data-phish-radar-for=["']([^"']+)["']/)?.[1];
        return scanBadges.filter(badge => !badge.removed && (!requestedId || badge.dataset.phishRadarFor === requestedId));
      }
      return [];
    },
    getElementById() { return null; }
  },
  getComputedStyle: () => ({ visibility: 'visible', display: 'block', opacity: '1' }),
  chrome: {
    storage: { onChanged: { addListener() {} } },
    runtime: {
      onMessage: { addListener() {} },
      sendMessage(message, callback) {
        messages.push(message);
        callback({ ok: true });
      }
    }
  }
});
for (const file of ['app-trust.js', 'analyzer.js']) {
  vm.runInContext(fs.readFileSync(path.join(extension, file), 'utf8'), context, { filename: file });
}
const content = fs.readFileSync(path.join(extension, 'content.js'), 'utf8');
const finalBoot = /\n\s*boot\(\);\s*\n\}\)\(\);\s*$/;
assert.match(content, finalBoot, 'the test-only instrumentation must replace only the final boot call');
vm.runInContext(content.replace(finalBoot, `
  globalThis.__linkTests = {
    resolveEffectiveUrl, linkOptions, shouldVisuallyMark, buildLinkTooltipHtml,
    handleClick, scanLinks, analyzeResolvedLink,
    configure(value) { settings = { ...settings, ...value }; }
  };
  // The separate floating summary UI is outside these link-state regressions.
  updateMiniPanel = () => {};
  // Spy on the actual click guard's uncertainty-notice call; rendering that
  // modal is independent of whether navigation is interrupted honestly.
  showRedirectLimitNotice = result => globalThis.__redirectNotices.push(result);
})();`), context, { filename: 'content.js' });
const helpers = context.__linkTests;
const shippedAnalyze = context.PhishRadarAnalyzer.analyzeUrl;

function anchor(href, text = 'Meta AI') {
  return {
    ...node(),
    innerText: text, textContent: text, title: '', target: '_blank', dataset: {},
    getAttribute(name) {
      if (name === 'href') return href;
      if (name === 'rel') return 'noopener noreferrer';
      return '';
    },
    setAttribute(name, value) { if (name === 'href') href = value; },
    closest(selector) { return selector === 'a[href]' ? this : null; },
    getClientRects: () => [{}],
    getBoundingClientRect: () => ({ width: 160, height: 30 }),
    parentElement: {},
    insertAdjacentElement(_position, badge) { scanBadges.push(badge); }
  };
}
function localScan(href, text = 'Meta AI') {
  const a = anchor(href, text);
  const resolved = helpers.resolveEffectiveUrl(href);
  const result = shippedAnalyze(resolved.effectiveUrl, helpers.linkOptions(a, resolved, 'feed'));
  return { a, resolved, result };
}
function wrapped(destination, host = 'l.facebook.com') {
  return `https://${host}/l.php?u=${encodeURIComponent(destination)}&h=tracking-only`;
}
function tooltip(score, resolved) {
  return helpers.buildLinkTooltipHtml({
    ...resolved, url: resolved.effectiveUrl,
    result: { score, levelText: 'น่าสงสัย', reasons: [], threatTypes: [] }
  });
}
const exactFile = path.join(workspace, 'output/meta-link-fix-20261009/user-link.json');
const syntheticMeta = 'https://www.meta.ai/?utm_source=facebook_bookmarks&fbclid=' + 'AbCdEf09_-'.repeat(18);
const userWrapper = fs.existsSync(exactFile)
  ? JSON.parse(fs.readFileSync(exactFile, 'utf8')).url
  : wrapped(syntheticMeta);
const userScan = localScan(userWrapper);
const expectedDestination = new URL(userWrapper).searchParams.get('u');
assert.equal(userScan.resolved.effectiveUrl, expectedDestination, 'Facebook link shim must resolve its u destination');
assert.equal(userScan.resolved.originalUrl, new URL(userWrapper).href, 'retain the original wrapper for an accurate UI caption');
assert.equal(userScan.resolved.wasRedirectWrapper, true);
assert.ok(userScan.result.score < 55, 'the Meta AI destination must remain below the existing feed decoration threshold');
assert.equal(helpers.shouldVisuallyMark(userScan.a, userScan.result, 'feed', userScan.resolved), false,
  'the user Meta AI bookmark must not receive a suspicious-link badge');
assert.equal(userScan.result.reasons.some(reason => reason.category === 'brand' && reason.points > 0), false,
  'Meta AI must not be accused of impersonating Facebook');

const mobileWrapper = helpers.resolveEffectiveUrl(wrapped('https://www.meta.ai/', 'lm.facebook.com'));
assert.equal(mobileWrapper.effectiveUrl, 'https://www.meta.ai/');
const googleWrapper = helpers.resolveEffectiveUrl('https://www.google.com/url?q=' + encodeURIComponent('https://www.meta.ai/'));
assert.equal(googleWrapper.effectiveUrl, 'https://www.meta.ai/');
const nestedWrapper = helpers.resolveEffectiveUrl('https://www.google.com/url?q=' + encodeURIComponent(userWrapper));
assert.equal(nestedWrapper.effectiveUrl, expectedDestination, 'known wrapper chains must reach their final checked destination');

// A benign URL hidden in an untrusted query must never replace the URL checked
// by the click guard. These cases would otherwise bypass destination evidence.
for (const badWrapper of [
  'https://facebook-login.evil.test/verify?u=' + encodeURIComponent('https://www.meta.ai/'),
  'https://l.facebook.com.evil.test/l.php?u=' + encodeURIComponent('https://www.meta.ai/'),
  'https://l.facebook.com/login?u=' + encodeURIComponent('https://www.meta.ai/'),
  'http://l.facebook.com/l.php?u=' + encodeURIComponent('https://www.meta.ai/'),
  'https://secret@l.facebook.com/l.php?u=' + encodeURIComponent('https://www.meta.ai/'),
  'https://l.facebook.com:8443/l.php?u=' + encodeURIComponent('https://www.meta.ai/'),
  'https://l.facebook.com/l.php?u=' + encodeURIComponent('https://www.meta.ai/') +
    '&u=' + encodeURIComponent('https://meta.ai.evil.test/login'),
  'https://www.google.com/url?q=' + encodeURIComponent('https://www.meta.ai/') +
    '&url=' + encodeURIComponent('https://meta.ai.evil.test/login'),
  'https://l.facebook.com/l.php?u=' + encodeURIComponent('https://www.meta.ai/') + '&password=secret',
  'https://l.facebook.com/l.php?u=' + encodeURIComponent('https://www.meta.ai/') + '&access_token=secret'
]) {
  const resolved = helpers.resolveEffectiveUrl(badWrapper);
  assert.equal(resolved.effectiveUrl, new URL(badWrapper).href, 'unsupported wrapper must remain the analyzed URL');
  assert.equal(resolved.wasRedirectWrapper, false);
}

const maliciousDestination = 'https://meta.ai.evil.test/login?password=secret';
const malicious = localScan(wrapped(maliciousDestination), 'Meta AI');
assert.equal(malicious.resolved.effectiveUrl, maliciousDestination);
assert.ok(malicious.result.score >= 60, 'official wrapper must not exempt a phishing destination');
assert.equal(helpers.shouldVisuallyMark(malicious.a, malicious.result, 'feed', malicious.resolved), true);
assert.ok(malicious.result.reasons.some(reason => reason.category === 'brand' && reason.points > 0));
const maliciousWithBenignNext = helpers.resolveEffectiveUrl(wrapped(
  maliciousDestination + '&next=' + encodeURIComponent('https://www.meta.ai/')));
assert.equal(new URL(maliciousWithBenignNext.effectiveUrl).hostname, 'meta.ai.evil.test',
  'do not continue unwrapping an arbitrary destination that embeds a benign next URL');

// Modern HTML gives target=_blank implicit noopener; only an explicit opener
// without a stronger noopener/noreferrer token establishes this local signal.
for (const [rel, expected] of [
  ['', false], ['noopener', false], ['noreferrer', false],
  ['opener', true], ['opener noopener', false], ['opener noreferrer', false],
  ['not-opener', false]
]) {
  const a = anchor('https://example.test/');
  const readAttribute = a.getAttribute.bind(a);
  a.getAttribute = name => name === 'rel' ? rel : readAttribute(name);
  assert.equal(helpers.linkOptions(a, { wasRedirectWrapper: false }, 'feed').opensNewTabNoNoopener,
    expected, `explicit opener evidence for rel=${JSON.stringify(rel)}`);
}

// Reusing a DOM link must not leave an old warning after a rescan, and a changed
// dangerous destination must update the tooltip without duplicate badges/hooks.
helpers.configure({ showStatusPanel: false, threshold: 60, pageScanningEnabled: true });
const legacyMeta = anchor(userWrapper);
Object.assign(legacyMeta.dataset, { phishRadarId: 'legacy-meta', phishRadarMarked: '1',
  phishRadarScore: '59', phishRadarReasons: 'old false positive',
  phishRadarTooltip: JSON.stringify({ result: { score: 59 } }), phishRadarTooltipBound: '1' });
legacyMeta.classList.add('phish-radar-link-target');
const legacyBadge = node();
legacyBadge.dataset.phishRadarFor = 'legacy-meta';
scanAnchors.push(legacyMeta);
scanBadges.push(legacyBadge);
const repairedScan = helpers.scanLinks();
assert.equal(repairedScan.shown, 0);
assert.equal(legacyMeta.classList.contains('phish-radar-link-target'), false);
assert.equal(legacyMeta.dataset.phishRadarMarked, undefined);
assert.equal(legacyMeta.dataset.phishRadarScore, undefined);
assert.equal(legacyMeta.dataset.phishRadarTooltip, undefined);
assert.equal(legacyBadge.removed, true, 'rescan must remove the old Meta AI badge');

scanAnchors.length = 0;
scanBadges.length = 0;
const changingLink = anchor(wrapped(maliciousDestination), 'Meta AI');
scanAnchors.push(changingLink);
helpers.scanLinks();
assert.equal(scanBadges.filter(badge => !badge.removed).length, 1);
const listenerCounts = JSON.stringify(changingLink.handlers);
const nextMalicious = 'https://facebook-login.evil.test/verify?password=secret';
changingLink.setAttribute('href', wrapped(nextMalicious));
helpers.scanLinks();
assert.equal(scanBadges.filter(badge => !badge.removed).length, 1, 'rescan must replace rather than duplicate badge');
assert.equal(JSON.parse(changingLink.dataset.phishRadarTooltip).url, nextMalicious);
assert.equal(JSON.stringify(changingLink.handlers), listenerCounts, 'rescan must retain one copy of each anchor listener');
changingLink.setAttribute('href', userWrapper);
helpers.scanLinks();
assert.equal(scanBadges.filter(badge => !badge.removed).length, 0, 'safe replacement destination clears its former warning');
assert.equal(changingLink.dataset.phishRadarTooltip, undefined);
scanAnchors.length = 0;
scanBadges.length = 0;

const unknown = localScan('https://independent-tool.example/?token=' + 'A'.repeat(45));
assert.ok(unknown.result.reasons.some(reason => reason.category === 'credential' && reason.points > 0),
  'a credential-like query on an unknown site must retain its evidence');

helpers.configure({ threshold: 60, pageScanningEnabled: true });
const below = tooltip(59, userScan.resolved);
assert.match(below, /RuleScore|Rule score|คะแนนจากกฎ|คะแนนกฎ/i,
  'the local link scanner score must identify its rule source rather than imply Random Forest');
assert.doesNotMatch(below, /ปลายทางจริงจาก redirect:.*l\.facebook\.com/,
  'wrapper caption must not label the intermediary as the actual destination');
assert.doesNotMatch(below, /ระบบจะเตือนก่อนเปิดเว็บ/,
  'a below-threshold tooltip must not promise navigation interruption');
const atWarning = tooltip(60, malicious.resolved);
assert.match(atWarning, /เตือน|ระวัง/, 'at-threshold tooltip must describe warning behavior');
helpers.configure({ threshold: 70 });
assert.doesNotMatch(tooltip(65, malicious.resolved), /ระบบจะเตือนก่อนเปิดเว็บ/,
  'tooltip warning claim must follow the configured threshold');

async function verifyClickBoundaries() {
  helpers.configure({ threshold: 60, pageScanningEnabled: true });
  // Refusing to unwrap an ambiguous/credential-bearing official shim must not
  // let its benign host cap hide an independently risky redirect candidate.
  const difficultWrappers = [
    wrapped(maliciousDestination) + '&password=secret',
    wrapped('https://www.meta.ai/') + '&u=' + encodeURIComponent(maliciousDestination),
    wrapped(maliciousDestination) + '&u=' + encodeURIComponent('https://www.meta.ai/'),
    'https://www.google.com/url?q=' + encodeURIComponent('https://www.meta.ai/') +
      '&url=' + encodeURIComponent(maliciousDestination)
  ];
  for (const href of difficultWrappers) {
    const a = anchor(href, 'Meta AI');
    scanAnchors.push(a);
    const scan = helpers.scanLinks();
    assert.ok(scan.high >= 1, 'known wrapper with any phishing redirect candidate must retain a high-risk scan');
    assert.ok(scan.items[0].score >= 60, 'official wrapper trust must not cap destination risk below warning');
    scanAnchors.length = 0;
    scanBadges.length = 0;
    messages.length = 0;
    let prevented = 0;
    await helpers.handleClick({ target: a,
      preventDefault() { prevented++; }, stopImmediatePropagation() {}
    });
    assert.equal(prevented, 1, 'actual click must be interrupted for a risky recognized redirect candidate');
    assert.ok(messages.some(message => message.type === 'OPEN_WARNING'));
  }
  const overflow = new URL('https://l.facebook.com/l.php');
  for (let index = 0; index < 16; index++) {
    overflow.searchParams.append('u', `https://www.meta.ai/?view=${index}`);
  }
  overflow.searchParams.append('u', maliciousDestination);
  let deepChain = maliciousDestination;
  for (let depth = 0; depth < 10; depth++) {
    deepChain = depth % 2 === 0
      ? wrapped(deepChain)
      : 'https://www.google.com/url?q=' + encodeURIComponent(deepChain);
  }
  for (const [label, href] of [['many redirect candidates', overflow.href], ['deep redirect chain', deepChain]]) {
    const a = anchor(href, 'Meta AI');
    const resolved = helpers.resolveEffectiveUrl(href);
    const baseline = shippedAnalyze(resolved.effectiveUrl, helpers.linkOptions(a, resolved, 'feed'));
    const result = helpers.analyzeResolvedLink(a, resolved, 'feed');
    const scoredUrl = result.redirectRiskUrl || resolved.effectiveUrl;
    const independentlyScored = shippedAnalyze(scoredUrl, helpers.linkOptions(a, resolved, 'feed'));
    assert.ok(baseline.score < 60, `${label}: this fixture isolates uncertainty from a scored warning`);
    assert.equal(result.redirectAssessmentLimited, true, `${label}: retain incomplete-assessment state`);
    assert.ok(result.score < 60, `${label}: the limit must not elevate the score to the warning threshold`);
    assert.equal(result.score, independentlyScored.score, `${label}: retain a score produced by the actual analyzer`);
    assert.ok(result.reasons.some(reason => reason.category === 'redirect' && reason.points === 0),
      `${label}: give the user a non-scoring explanation of the assessment limit`);
    messages.length = 0;
    redirectNotices.length = 0;
    let prevented = 0;
    let stopped = 0;
    await helpers.handleClick({ target: a,
      preventDefault() { prevented++; }, stopImmediatePropagation() { stopped++; }
    });
    assert.equal(prevented, 1, `${label}: do not silently navigate to an incompletely checked redirect`);
    assert.equal(stopped, 1, `${label}: stop the page's navigation event`);
    assert.equal(redirectNotices.length, 1, `${label}: display a dedicated uncertainty notice`);
    assert.equal(redirectNotices[0].redirectAssessmentLimited, true);
    assert.equal(redirectNotices[0].score, independentlyScored.score);
    assert.equal(messages.some(message => message.type === 'OPEN_WARNING'), false,
      `${label}: do not substitute the ordinary scored-risk warning`);
  }
  for (const score of [59, 60, 79, 80]) {
    let prevented = 0;
    let stopped = 0;
    messages.length = 0;
    context.PhishRadarAnalyzer.analyzeUrl = () => ({ score, reasons: [], url: maliciousDestination });
    const a = anchor(wrapped(maliciousDestination));
    await helpers.handleClick({ target: a,
      preventDefault() { prevented++; },
      stopImmediatePropagation() { stopped++; }
    });
    const warning = messages.find(message => message.type === 'OPEN_WARNING');
    assert.equal(prevented, score >= 60 ? 1 : 0, `prevent navigation at score ${score}`);
    assert.equal(stopped, score >= 60 ? 1 : 0, `stop event propagation at score ${score}`);
    assert.equal(Boolean(warning), score >= 60, `warning request boundary at score ${score}`);
    if (warning) assert.equal(warning.target, maliciousDestination, 'warning receives the checked destination');
  }
  context.PhishRadarAnalyzer.analyzeUrl = shippedAnalyze;
  console.log(JSON.stringify({ ok: true, metaAiScore: userScan.result.score,
    maliciousDestinationScore: malicious.result.score,
    clickBoundaries: { 59: 'allow', 60: 'warn', 79: 'warn', 80: 'warn-request' } }));
}
verifyClickBoundaries().catch(error => { console.error(error); process.exitCode = 1; });
