const assert = require('node:assert/strict');
const path = require('node:path');

const analyzerPaths = [
  path.resolve(__dirname, '..', 'analyzer.js'),
  path.resolve(__dirname, '..', 'web-app', 'analyzer.js')
];

for (const analyzerPath of analyzerPaths) {
  const analyzer = require(analyzerPath);
  assert.equal(typeof analyzer.analyzeUrl, 'function', analyzerPath + ' must export analyzeUrl');

  const safeResult = analyzer.analyzeUrl('https://www.google.com/');
  const riskyResult = analyzer.analyzeUrl(
    'http://paypal-login-verify.top/account/otp?redirect=https%3A%2F%2Fevil.example'
  );

  assert.equal(typeof safeResult.score, 'number');
  assert.equal(typeof riskyResult.score, 'number');
  assert.ok(safeResult.score < riskyResult.score, analyzerPath + ' should rank the phishing sample higher');
  assert.ok(riskyResult.score >= 61, analyzerPath + ' should flag the phishing sample as high risk');
}

console.log('Analyzer smoke tests passed for ' + analyzerPaths.length + ' runtimes.');
