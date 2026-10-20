"""One inventory for delivery manifests and packaging (Python standard library)."""
from pathlib import Path
import hashlib

EXPERIMENT = 'experiments/aclt-minimal-verifier-state3'
MULTINODE = 'experiments/aclt-multinode-admission'
AUTHORITY = 'experiments/aclt-authority-admission'
EXCLUDE = {'target', 'build', '.toolchain', '__pycache__', '.git', 'artifacts', 'dist'}

def files(root, directory):
    base = root / directory
    result = []
    for path in sorted(base.rglob('*')):
        relative = path.relative_to(root)
        historical = relative.as_posix().startswith('docs/workflow/example/')
        blocked = EXCLUDE - {'build', 'artifacts'} if historical else EXCLUDE
        if blocked.intersection(path.relative_to(base).parts):
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink is not a delivery input: {relative}')
        if relative.as_posix() == MULTINODE + '/local-tests.json':
            continue
        if path.is_file():
            result.append(path)
    return result

def manifest(root, paths):
    return ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n'
                   for p in sorted(set(paths)))

def inventories(root):
    workflow = files(root, 'docs/workflow') + files(root, 'tests/workflow')
    workflow += [root / name for name in [
        '.aclt-flow/template.json', '.aclt-flow/.gitignore', 'scripts/aclt-flow.py',
        'scripts/package-singlehost.py', 'scripts/repository_files.py']]
    delivery = []
    for directory in ['tools', 'tests', 'schemas', 'registries', 'scripts', 'docs', EXPERIMENT, MULTINODE, AUTHORITY]:
        delivery.extend(p for p in files(root, directory)
                        if not p.relative_to(root).as_posix().startswith('docs/codocs/'))
    delivery += [root / name for name in [
        'README.md', 'CONTRIBUTING.md', 'LICENSE', 'Makefile', '.gitignore',
        '.aclt-flow/template.json', '.aclt-flow/.gitignore', 'WORKFLOW-SHA256SUMS',
        'experiments/README.md']]
    return {
        EXPERIMENT + '/SHA256SUMS': (root / EXPERIMENT, [
            p for p in files(root, EXPERIMENT) if p.name != 'SHA256SUMS']),
        MULTINODE + '/SHA256SUMS': (root / MULTINODE, [
            p for p in files(root, MULTINODE) if p.name != 'SHA256SUMS']),
        AUTHORITY + '/SHA256SUMS': (root / AUTHORITY, [
            p for p in files(root, AUTHORITY) if p.name != 'SHA256SUMS']),
        'WORKFLOW-SHA256SUMS': (root, workflow),
        'SINGLEHOST-SHA256SUMS': (root, delivery),
    }

def refresh(root):
    for name, (base, paths) in inventories(root).items():
        (root / name).write_text(manifest(base, paths))

def verify(root):
    errors = []
    for name, (base, paths) in inventories(root).items():
        target = root / name
        if not target.is_file() or target.read_text() != manifest(base, paths):
            errors.append(name)
    return errors
