import os

root = os.path.dirname(os.path.abspath(__file__))

# Scripts to inject globally
GLOBAL_SCRIPTS = [
    '<script src="assets/js/affiliate-tracker.js" defer></script>',
    '<script src="assets/js/realtime-notifications.js" defer></script>'
]

# Scripts to inject only on index.html
INDEX_EXTRA = [
    '<script src="assets/js/ab-test.js" defer></script>'
]

for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    for fname in filenames:
        if not fname.endswith('.html'):
            continue
        fpath = os.path.join(dirpath, fname)
        relpath = os.path.relpath(fpath, root)
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        changed = False
        for script in GLOBAL_SCRIPTS:
            if script not in content:
                content = content.replace('</body>', f'{script}\n</body>')
                changed = True

        if fname.lower() == 'index.html':
            for script in INDEX_EXTRA:
                if script not in content:
                    content = content.replace('</body>', f'{script}\n</body>')
                    changed = True

        if changed:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            print('Injected features into:', relpath)

print('Done.')
