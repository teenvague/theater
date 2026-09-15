"""Summarize the actual published snapshot in the scheduled run's job summary."""
import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def report(root=ROOT):
    data = json.loads((root / 'dist/data/shows.json').read_text())
    productions = data['productions']
    missing = [p['title'] for p in productions if not p.get('image')]
    broken = [p['title'] for p in productions if p.get('image', '').startswith('images/') and not (root / 'dist' / p['image']).is_file()]
    text = f"## Production artwork\n\n{len(productions)-len(missing)} of {len(productions)} productions have images.\n"
    if missing:
        text += '\nStill awaiting artwork:\n' + ''.join('- ' + t + '\n' for t in missing)
    if broken:
        text += '\nMissing local files:\n' + ''.join('- ' + t + '\n' for t in broken)
    return text, broken

if __name__ == '__main__':
    text, broken = report()
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write(text)
    raise SystemExit(1 if broken else 0)
