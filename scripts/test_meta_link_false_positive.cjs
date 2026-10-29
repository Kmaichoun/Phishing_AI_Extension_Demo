'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

// The submitted Facebook bookmark resolves to this 239-character URL. The
// link options reproduce the local tooltip score, not the backend RF score.
const submittedMetaDestination = 'https://www.meta.ai/?utm_source=facebook_bookmarks&fbclid=IwZXh0bgNhZW0CMTAAcGRvZgVicmlkETFDeGVlcjM5NGFOSnpzQ1Ryc3J0YwZhcHBfaWQQMjIyMDM5MTc4ODIwMDg5MgABHj_y5LjHD6aEbDDs6WwbRTFrtEC22VIGnLD-gSe6oHIEBrVkZWn4QO_R1aW1_aem_bTvbPqgLm4Y2bXWdMNUAQw';
const opaqueTracking = 'AbCdEf0123456789_-'.repeat(10);
const secretValue = 'SyntheticCredential1234567890';
const isPositiveCategory = (result, category) => result.reasons.some(reason => reason.points > 0 && reason.category === category);

function benignTracking(result, runtime, id, expectOfficial = false) {
  const label = `${runtime}: ${id}`;
  assert(!isPositiveCategory(result, 'credential'), `${label}: tracking was incorrectly described as credentials`);
  assert(!isPositiveCategory(result, 'combo'), `${label}: tracking created a phishing combination`);
  if (expectOfficial) {
    assert(result.features.officialBrand.includes('facebook'), `${label}: Meta's official domain was not recognized`);
    assert(!isPositiveCategory(result, 'brand'), `${label}: official Meta domain was described as an impersonation`);
    assert(result.score < 31, `${label}: local tooltip still warns on an ordinary Meta bookmark (${result.score})`);
  }
}

const cases = [
  {
    id: 'submitted-meta-bookmark', url: submittedMetaDestination,
    options: {linkText: 'Meta AI', opensNewTabNoNoopener: true},
    verify: (result, runtime, id) => benignTracking(result, runtime, id, true)
  },
  ...['https://meta.ai/', 'https://www.meta.ai/', 'https://chat.meta.ai/'].map(url => ({
    id: `official-${new URL(url).hostname}`, url,
    verify: (result, runtime, id) => benignTracking(result, runtime, id, true)
  })),
  ...['fbclid', 'utm_content', 'tracking_id', 'asession', 'mytoken', 'wrongprefixsession', 'prefixpassword'].map(key => ({
    id: `non-credential-query-${key}`, url: `https://example.org/article?${key}=${opaqueTracking}`,
    verify: (result, runtime, id) => benignTracking(result, runtime, id)
  })),
  {
    id: 'encoded-incidental-query-key', url: `https://example.org/article?%6Dy%74oken=${opaqueTracking}`,
    verify: (result, runtime, id) => benignTracking(result, runtime, id)
  },
  ...['meta.ai.evil.example', 'www.meta.ai.evil.example', 'meta-ai.example'].map(hostname => ({
    id: `spoof-with-tracking-only-${hostname}`, url: `https://${hostname}/article?fbclid=${opaqueTracking}`,
    verify(result, runtime, id) {
      const label = `${runtime}: ${id}`;
      assert(!result.features.officialBrand.includes('facebook'), `${label}: spoofed host gained official-domain trust`);
      assert(isPositiveCategory(result, 'brand'), `${label}: host impersonation evidence disappeared`);
      assert(!isPositiveCategory(result, 'credential'), `${label}: tracking alone fabricated credentials`);
      assert(!isPositiveCategory(result, 'combo'), `${label}: tracking alone fabricated a credential combination`);
    }
  })),
  ...['meta.ai.evil.example', 'www.meta.ai.evil.example', 'meta-ai.example', 'evilmeta.ai'].map(hostname => ({
    id: `spoof-${hostname}`, url: `https://${hostname}/login?password=${secretValue}`,
    verify(result, runtime, id) {
      const label = `${runtime}: ${id}`;
      assert(!result.features.officialBrand.includes('facebook'), `${label}: suffix/embedded brand gained official Meta trust`);
      assert(isPositiveCategory(result, 'credential'), `${label}: lost actual credentials`);
      // Embedded "evilmeta" does not trigger the existing exact-token brand
      // rule. This case verifies the official-domain boundary, not a new rule.
      if (hostname !== 'evilmeta.ai') {
        assert(isPositiveCategory(result, 'brand'), `${label}: lost impersonation evidence`);
        assert(isPositiveCategory(result, 'combo'), `${label}: lost impersonation plus credentials combination`);
        assert(result.score >= 60, `${label}: credential-bearing Meta impersonation no longer warns`);
      }
    }
  })),
  ...['password', 'passwd', 'otp', 'token', 'session', 'access_token', 'session_id', 'private_key'].map(key => ({
    id: `actual-query-credential-${key}`, url: `https://example.org/?${key}=${key === 'otp' ? '123456' : secretValue}`,
    verify(result, runtime, id) {
      assert(isPositiveCategory(result, 'credential'), `${runtime}: ${id}: genuine credential parameter lost its evidence`);
      // session_id had keyword evidence rather than a 24-point query finding
      // before this repair. For the other keys, preserve the existing finding.
      if (key !== 'session_id') {
        assert(result.reasons.some(reason => reason.points >= 24 && reason.category === 'credential'), `${runtime}: ${id}: genuine credential query parameter lost its query evidence`);
      }
    }
  })),
  {
    id: 'encoded-real-credential-key', url: `https://example.org/?%70assword=${secretValue}`,
    verify(result, runtime, id) {
      assert(isPositiveCategory(result, 'credential'), `${runtime}: ${id}: encoded credential parameter was ignored`);
    }
  },
  ...['password', 'token'].map(key => ({
    id: `empty-credential-query-${key}`, url: `https://example.org/?${key}=`,
    verify(result, runtime, id) {
      assert(!result.reasons.some(reason => reason.points >= 24 && reason.category === 'credential'), `${runtime}: ${id}: an empty value was described as sending a secret`);
    }
  })),
  {
    id: 'official-domain-with-real-secret', url: `https://www.meta.ai/?password=${secretValue}`,
    verify(result, runtime, id) {
      assert(result.features.officialBrand.includes('facebook'), `${runtime}: ${id}: missing official-domain recognition`);
      assert(isPositiveCategory(result, 'credential'), `${runtime}: ${id}: official-domain recognition hid a credential anomaly`);
    }
  },
  {
    id: 'external-credential-redirect',
    url: `https://meta.ai.evil.example/login?next=${encodeURIComponent(`https://collector.example/?password=${secretValue}`)}`,
    verify(result, runtime, id) {
      assert(isPositiveCategory(result, 'brand'), `${runtime}: ${id}: lost impersonation evidence`);
      assert(isPositiveCategory(result, 'redirect'), `${runtime}: ${id}: external redirect disappeared`);
      assert(isPositiveCategory(result, 'credential'), `${runtime}: ${id}: credential-bearing nested destination disappeared`);
    }
  },
  {
    id: 'official-looking-userinfo', url: `https://www.meta.ai:${secretValue}@collector.example/`,
    verify(result, runtime, id) {
      assert(!result.features.officialBrand.includes('facebook'), `${runtime}: ${id}: userinfo gained official Meta trust`);
      assert(result.reasons.some(reason => reason.points > 0 && reason.label.includes('userinfo')), `${runtime}: ${id}: lost userinfo evidence`);
    }
  },
  {
    id: 'existing-high-risk-paypal', url: 'http://paypal-login-verify.top/account/otp?redirect=https%3A%2F%2Fevil.example',
    verify(result, runtime, id) {
      assert(isPositiveCategory(result, 'brand'), `${runtime}: ${id}: existing impersonation signal disappeared`);
      assert(isPositiveCategory(result, 'credential'), `${runtime}: ${id}: existing OTP signal disappeared`);
      assert(result.score >= 80, `${runtime}: ${id}: existing dangerous fixture no longer reaches block threshold`);
    }
  }
];

assert.equal(submittedMetaDestination.length, 239, 'submitted bookmark fixture length changed');
const baselineMode = process.argv.includes('--baseline');
const analyzerRootIndex = process.argv.indexOf('--analyzer-root');
if (analyzerRootIndex >= 0) assert(process.argv[analyzerRootIndex + 1], '--analyzer-root requires a directory');
const analyzerRoot = analyzerRootIndex >= 0 ? path.resolve(process.argv[analyzerRootIndex + 1]) : path.join(__dirname, '..');
const results = [];
for (const runtime of ['extension', 'web-app']) {
  const analyzer = require(path.join(analyzerRoot, runtime, 'analyzer.js'));
  for (const test of cases) {
    const result = analyzer.analyzeUrl(test.url, test.options || {});
    if (!baselineMode) test.verify(result, runtime, test.id);
    results.push({
      runtime, id: test.id, score: result.score,
      officialBrand: result.features.officialBrand,
      positiveCategories: [...new Set(result.reasons.filter(reason => reason.points > 0).map(reason => reason.category))],
      reasons: result.reasons.map(({points, category, label}) => ({points, category, label}))
    });
  }
}
const report = {
  kind: baselineMode ? 'baseline' : 'regression-results',
  scope: 'Specific URL-rule regressions in two runtimes; not population FPR, RF accuracy, or a safety guarantee.',
  casesPerRuntime: cases.length, results
};
if (baselineMode || process.argv.includes('--json')) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(`Meta-link regressions passed: ${cases.length} cases in each of 2 analyzer runtimes (${results.length} checks).`);
  console.log(JSON.stringify(results.filter(result => result.id === 'submitted-meta-bookmark').map(({runtime, score, officialBrand, positiveCategories}) => ({runtime, score, officialBrand, positiveCategories})), null, 2));
}
