#!/usr/bin/env python3
"""Refresh delivery checksums after intentional source/report changes."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/aclt-minimal-verifier-state3'
EXCLUDE = {'target', 'build', '.toolchain', '__pycache__', '.git'}

def files(directory):
    excluded = EXCLUDE - {'build'} if directory == ROOT / 'docs/workflow' else EXCLUDE
    return [p for p in directory.rglob('*') if p.is_file()
            and not excluded.intersection(p.relative_to(directory).parts)]

def manifest(root, paths):
    return ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n'
                   for p in sorted(set(paths)))

def main():
    (EXPERIMENT / 'SHA256SUMS').write_text(manifest(EXPERIMENT, [p for p in files(EXPERIMENT) if p.name != 'SHA256SUMS']))
    workflow = files(ROOT / 'docs/workflow') + files(ROOT / 'tests/workflow')
    workflow += [ROOT / p for p in ['.aclt-flow/template.json', '.aclt-flow/.gitignore', 'scripts/aclt-flow.py', 'scripts/package-singlehost.py']]
    (ROOT / 'WORKFLOW-SHA256SUMS').write_text(manifest(ROOT, workflow))
    delivery = []
    for directory in ['tools', 'tests', 'schemas', 'scripts', 'docs/testing', 'docs/workflow', 'experiments/aclt-minimal-verifier-state3']:
        delivery.extend(files(ROOT / directory))
    delivery += [ROOT / p for p in ['.gitignore', '.aclt-flow/template.json', '.aclt-flow/.gitignore', 'WORKFLOW-SHA256SUMS', 'experiments/README.md', 'docs/07-roadmap/current-status.md', 'docs/07-roadmap/open-questions.md']]
    (ROOT / 'SINGLEHOST-SHA256SUMS').write_text(manifest(ROOT, delivery))

if __name__ == '__main__':
    main()
