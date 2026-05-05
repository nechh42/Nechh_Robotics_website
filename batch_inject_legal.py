import os
import re

LEGAL_SCRIPT = '<script src="assets/js/legal-modal.js" defer></script>'

root = os.path.dirname(os.path.abspath(__file__))

for dirpath, dirnames, filenames in os.walk(root):
    # Skip .git and other hidden dirs
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    for fname in filenames:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        if LEGAL_SCRIPT in content:
            continue
        # Insert before closing </body> if present
        if '</body>' in content:
            content = content.replace('</body>', f'{LEGAL_SCRIPT}\n</body>')
        else:
            content += '\n' + LEGAL_SCRIPT
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print('Injected:', os.path.relpath(fpath, root))

print('Done.')
