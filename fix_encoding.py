import os

replacements = {
    '\u00e2\u20ac\u201c': '\u2014',  # em dash
    '\u00e2\u20ac\u201d': '\u2013',  # en dash
    '\u00e2\u2020\u2019': '\u2192',  # right arrow
    '\u00e2\u201a\u00bf': '\u20bf',  # bitcoin sign
    '\u00e2\u0153\u2026': '\u2705',  # check box green
    '\u00e2\u0153\u201c': '\u2714',  # heavy check
    '\u00e2\u0153\u02c6': '\u2708',  # airplane
    '\u00e2\u009a ': '\u26a0',       # warning
    '\u00e2\u009a\u2013': '\u2696',  # scales
    '\u00e2\u009a\u201c': '\u2694',  # swords
    '\u00e2\u0153\u2014': '\u2717',  # x mark
    '\u00e2\u0153\u2019': '\u2714',  # check
}

def fix_file(fname):
    try:
        c = open(fname, encoding='utf-8').read()
        changed = 0
        for bad, good in replacements.items():
            if bad in c:
                c = c.replace(bad, good)
                changed += 1
        if changed:
            open(fname, 'w', encoding='utf-8').write(c)
            print(f'{fname}: {changed} fixes')
        return changed
    except Exception as e:
        print(f'SKIP {fname}: {e}')
        return 0

files = [f for f in os.listdir('.') if f.endswith('.html')]
for sub in ['blog', 'legal']:
    if os.path.isdir(sub):
        files += [sub + '/' + f for f in os.listdir(sub) if f.endswith('.html')]

total = sum(fix_file(f) for f in files)
print(f'\nTotal replacements: {total} in {len(files)} files')
