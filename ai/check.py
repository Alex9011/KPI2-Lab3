#!/usr/bin/env python3
"""Structural cross-check: 8 Gherkin scenarios -> Mermaid -> SVG/PNG and links."""
from pathlib import Path
import re
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=(ROOT/'spec.md').read_text(encoding='utf8')
files=sorted((ROOT/'sequence').glob('S-*.mmd'))
assert len(files)==8,f'Expected 8 diagrams, got {len(files)}'
errors=[]
for i,f in enumerate(files,1):
    id=f'S-{i:02}'
    if not f.name.startswith(id+'-'):errors.append(f'wrong order {f}')
    src=f.read_text(encoding='utf8')
    if not src.strip().startswith('sequenceDiagram'):errors.append(f'no sequenceDiagram: {f.name}')
    if f'**{id}.' not in spec: errors.append(f'missing {id} in spec')
    if not re.search(r'(?m)^\s*(alt|opt|loop|par)\s+\S',src): errors.append(f'no combined fragment {f.name}')
    if '-->>' not in src:errors.append(f'no return {f.name}')
    if len(re.findall(r'(?m)^\s*activate\s+',src))!=len(re.findall(r'(?m)^\s*deactivate\s+',src)): errors.append(f'activation imbalance {f.name}')
    frag_open=len(re.findall(r'(?m)^\s*(?:alt|opt|loop|par)\s',src)); frag_end=len(re.findall(r'(?m)^\s*end\s*$',src))
    if frag_open!=frag_end:errors.append(f'fragment imbalance {f.name}: {frag_open} != {frag_end}')
    if 'warehouse' in src.lower() or 'supplier' in src.lower():errors.append(f'non-library words {f.name}')
    if 'Copy.available' in src:errors.append(f'invented attribute {f.name}')
    for ext in ('svg','png'):
        path=ROOT/'render'/(f.stem+'.'+ext)
        if not path.exists():errors.append(f'missing render: {path.name}')
        elif path.stat().st_size<1000:errors.append(f'tiny/empty render: {path.name}')
        if ext=='svg' and path.exists():
            ET.parse(path)
    print(id, f.name, 'ok')
# markdown local file links in project docs
for d in ('spec.md','DEFENSE.md','README.md'):
    body=(ROOT/d).read_text(encoding='utf8')
    for path in re.findall(r'\]\(([^)]+)\)',body):
        if path.startswith(('http://','https://','#')):continue
        if not (ROOT/path.split('#')[0]).exists():errors.append(f'bad local link in {d}: {path}')
assert len(re.findall(r'(?m)^\*\*S-\d\d\.',spec))==8,'Missing Gherkin scenarios'
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print('PASS: 8 Gherkin = 8 Mermaid sources = 8 SVG + 8 PNG; activation/fragment pairs and local links validated.')
