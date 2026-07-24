const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectRoot = path.resolve(__dirname, '..');
const appTrust = require(path.join(projectRoot, 'app-trust.js'));

const trustedUrls = [
  'http://app.phishradar.localhost:5505/',
  'http://app.phishradar.localhost:5505/login.html?next=index.html',
  'http://127.0.0.1:5505/',
  'http://localhost:5505/settings.html'
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

const runtimeSource = fs.readFileSync(path.join(projectRoot, 'web-app', 'runtime-config.js'), 'utf8');
const runtimeContext = {
  location: {
    hostname: 'app.phishradar.localhost',
    origin: 'http://app.phishradar.localhost:5505'
  }
};
runtimeContext.globalThis = runtimeContext;
vm.runInNewContext(runtimeSource, runtimeContext, { filename: 'runtime-config.js' });
assert.equal(runtimeContext.PhishRadarRuntime.apiBase, 'http://api.phishradar.localhost:8765');
assert.equal(runtimeContext.PhishRadarRuntime.isLocalDomain, true);

console.log('Trusted Web App origin tests passed.');
