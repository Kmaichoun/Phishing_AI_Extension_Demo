import '../../analyzer.js';

const analyzer = globalThis.PhishRadarAnalyzer;

if (!analyzer?.analyzeUrl) {
  throw new Error('Phish Radar analyzer could not be loaded.');
}

export default analyzer;
