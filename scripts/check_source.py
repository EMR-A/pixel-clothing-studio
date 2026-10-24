# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Check the publishable source allowlist without accessing accounts or the game."""
from pathlib import Path
import ast,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES={'src','tests','scripts','docs','licenses','.github'}
FILES={'LICENSE','README.md','THIRD_PARTY_NOTICES.md','.gitignore','.gitattributes','requirements.txt','package.json'}
DENIED_SUFFIXES={'.ydd','.ytd','.yft','.ydr','.ybn','.rpf','.blend','.exe','.dll','.pyd','.whl','.zip'}

def publishable_files():
    for name in sorted(FILES):
        path=ROOT/name
        if path.is_file():yield path
    for folder in sorted(DIRECTORIES):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.pyo']:yield path

def check():
    files=list(publishable_files());errors=[]
    for path in files:
        rel=path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):errors.append('Linked file: '+rel);continue
        if path.suffix.lower() in DENIED_SUFFIXES:errors.append('Binary or asset: '+rel);continue
        if any(p.lower()=='pymateria' or p.lower().startswith(('pymateria-','pymateria.')) for p in path.parts):errors.append('Restricted dependency: '+rel)
        if path.stat().st_size>2*1024*1024:errors.append('Unexpectedly large source file: '+rel)
        try:text=path.read_text('utf-8')
        except UnicodeError:errors.append('Non-text file: '+rel);continue
        if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|private_[A-Za-z0-9+/=]{24,})',text):errors.append('Potential real credential: '+rel)
        if re.search(r'[A-Za-z]:[/\\]Users[/\\](?!Public\b|Customer\b)',text):errors.append('Personal Windows path: '+rel)
        if path.suffix in ['.py','.pyw']:
            try:ast.parse(text)
            except SyntaxError as exc:errors.append('Python syntax: '+rel+': '+str(exc))
        if path.suffix=='.json':json.loads(text)
    required=['src/app.pyw','src/locales.json','LICENSE','THIRD_PARTY_NOTICES.md','docs/BUILD.md','docs/RELEASING.md','.gitignore']
    for relative in required:
        if not (ROOT/relative).is_file():errors.append('Missing file: '+relative)
    locales=json.loads((ROOT/'src/locales.json').read_text('utf-8'));assert len(locales['languages'])==18
    if errors:raise ValueError('\n'.join(errors))
    return files

if __name__=='__main__':
    try:print(json.dumps({'status':'passed','publishableFiles':len(check()),'runtimeBinariesIncluded':False,'gameAssetsIncluded':False}))
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
