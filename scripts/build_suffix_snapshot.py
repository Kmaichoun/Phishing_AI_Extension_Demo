"""Vendor the ICANN rules shipped with pinned tldextract 5.3.2; no network calls.

PSL is Mozilla Public License 2.0: https://publicsuffix.org/list/
Keep the original snapshot (including attribution) and generated browser blocks.
"""
import json
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = files('tldextract').joinpath('.tld_set_snapshot').read_text(encoding='utf-8')
(ROOT / 'backend/public_suffix_list.SOURCE.txt').write_text(source, encoding='utf-8')
icann = source.split('// ===BEGIN ICANN DOMAINS===')[1].split('// ===END ICANN DOMAINS===')[0]
rules = []
for line in icann.splitlines():
    line = line.strip()
    if line and not line.startswith('//'):
        prefix = '! ' if line.startswith('!') else '* ' if line.startswith('*.') else ''
        value = line.lstrip('!').removeprefix('*.').encode('idna').decode('ascii')
        rules.append(('!' if prefix == '! ' else '*.' if prefix else '') + value)
(ROOT / 'backend/public_suffix_list.dat').write_text('\n'.join(rules) + '\n', encoding='utf-8')
block = '''  // BEGIN GENERATED PSL: MPL-2.0, publicsuffix.org; scripts/build_suffix_snapshot.py
  const PUBLIC_SUFFIX_RULES = new Set(__RULES__.split(' '));
  function getRegistrableGuess(hostname) {
    const clean = String(hostname || '').toLowerCase().replace(/^www\\./, '').replace(/\\.$/, '');
    if (/^\\d{1,3}(\\.\\d{1,3}){3}$/.test(clean) || clean.includes(':')) return clean;
    const labels = clean.split('.').filter(Boolean);
    let suffixSize = 1;
    for (let i = 0; i < labels.length; i++) {
      const tail = labels.slice(i).join('.');
      if (PUBLIC_SUFFIX_RULES.has('!' + tail)) { suffixSize = labels.length - i - 1; break; }
      if (PUBLIC_SUFFIX_RULES.has(tail) || (i + 1 < labels.length && PUBLIC_SUFFIX_RULES.has('*.' + labels.slice(i + 1).join('.')))) {
        suffixSize = Math.max(suffixSize, labels.length - i);
      }
    }
    return labels.slice(-Math.min(labels.length, suffixSize + 1)).join('.');
  }
  // END GENERATED PSL
'''.replace('__RULES__', json.dumps(' '.join(rules)))
for relative in ['web-app/analyzer.js', 'extension/analyzer.js']:
    path = ROOT / relative
    text = path.read_text(encoding='utf-8')
    start = text.find('  // BEGIN GENERATED PSL')
    if start < 0:
        start = text.index('  function getRegistrableGuess(')
    end = text.index('  function isSubdomainOrSame(', start)
    path.write_text(text[:start] + block + '\n' + text[end:], encoding='utf-8')
print(f'Generated {len(rules)} ICANN suffix rules in both analyzers and backend.')
