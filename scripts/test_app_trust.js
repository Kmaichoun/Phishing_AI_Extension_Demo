const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '..');
const appTrust = require(path.join(projectRoot, 'extension', 'app-trust.js'));

assert.equal(
  appTrust.DEFAULT_WEB_APP_URL,
  'http://app.phishradar.localhost:5505/#/login',
  'Extension login entry must use the React hash route'
);

const trustedUrls = [
  'http://app.phishradar.localhost:5505/',
  'http://app.phishradar.localhost:5505/#/login',
  'http://127.0.0.1:5505/#/scan',
  'http://localhost:5505/#/settings'
];

for (const url of trustedUrls) {
  assert.equal(appTrust.isTrustedWebAppUrl(url), true, `${url} must be trusted`);
  const result = appTrust.createTrustedResult(url);
  assert.equal(result.trustedWebApp, true);
  assert.equal(result.score, 0);
}

const rejectedUrls = [
  'http://app.phishradar.localhost:5506/',
  'https://app.phishradar.localhost:5505/',
  'http://api.phishradar.localhost:8765/health',
  'http://127.0.0.1:8765/',
  'http://127.0.0.1.evil.example:5505/',
  'http://app.phishradar.localhost.evil.example:5505/',
  'javascript:alert(1)',
  'not a url'
];

for (const url of rejectedUrls) {
  assert.equal(appTrust.isTrustedWebAppUrl(url), false, `${url} must not be trusted`);
}

const runtimeSource = fs.readFileSync(
  path.join(projectRoot, 'web-app', 'src', 'services', 'runtime.js'),
  'utf8'
);
assert.ok(
  runtimeSource.includes("'app.phishradar.localhost': 'http://api.phishradar.localhost:8765'"),
  'React runtime must map the local Web App domain to the local API domain'
);
assert.ok(
  runtimeSource.includes("'127.0.0.1': 'http://127.0.0.1:8765'"),
  'React runtime must support the 127.0.0.1 fallback'
);
assert.ok(
  runtimeSource.includes('import.meta.env.VITE_API_BASE'),
  'React runtime must support VITE_API_BASE'
);

console.log('Trusted Web App origin tests passed.');
