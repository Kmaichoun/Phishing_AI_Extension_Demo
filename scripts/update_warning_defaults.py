"""One-time migration of explicit warning defaults; preserve other numeric values."""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
paths = [ROOT / 'backend/app.py', ROOT / 'backend/llm_explainer.py',
         ROOT / 'web-app/analyzer.js', ROOT / 'web-app/src/services/risk.js',
         ROOT / 'web-app/src/components/WorkspaceUi.jsx', ROOT / 'web-app/src/contexts/AppContext.jsx',
         *sorted((ROOT / 'extension').glob('*.js'))]
for path in paths:
    original = path.read_text(encoding='utf-8')
    # These occurrences are all warning defaults / category boundaries, verified
    # in the source inventory. PSL data and other numeric literals are untouched.
    changed = re.sub(r'(?<![\w.])61(?:\.0)?(?![\w.])',
                     lambda m: '60.0' if m[0].endswith('.0') else '60', original)
    changed = re.sub(r'(?<![\w.])81(?:\.0)?(?![\w.])',
                     lambda m: '80.0' if m[0].endswith('.0') else '80', changed)
    if original == changed:
        continue
    backup = ROOT / 'output/warning60-20261007/before' / path.relative_to(ROOT)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copyfile(path, backup)
    path.write_text(changed, encoding='utf-8')
    print(path.relative_to(ROOT))
