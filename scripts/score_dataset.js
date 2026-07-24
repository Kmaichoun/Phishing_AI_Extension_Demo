'use strict';

/*
 * Batch bridge between the training pipeline and the exact RuleScore engine
 * used by the web app. Input is a JSON array of URL strings on stdin; output
 * is a JSON array of integer scores on stdout.
 */
const profile = process.argv.includes('--extension') ? 'extension' : 'web';
const analyzer = profile === 'extension'
  ? require('../analyzer.js')
  : require('../web-app/analyzer.js');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
});

process.stdin.on('end', () => {
  try {
    const urls = JSON.parse(input || '[]');
    if (!Array.isArray(urls)) throw new TypeError('Input must be a JSON array.');

    const scores = urls.map(url => {
      const result = analyzer.analyzeUrl(String(url || ''));
      const score = Number(result && result.score);
      if (!Number.isFinite(score)) throw new Error(`Analyzer returned no score for ${url}`);
      return Math.max(0, Math.min(100, Math.round(score)));
    });

    process.stdout.write(JSON.stringify(scores));
  } catch (error) {
    process.stderr.write(`${error.stack || error.message || error}\n`);
    process.exitCode = 1;
  }
});
