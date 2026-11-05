"""One inventory for delivery manifests and packaging (Python standard library)."""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.git_sources import git
import fnmatch

EXPERIMENT = 'experiments/aclt-minimal-verifier-state3'
MULTINODE = 'experiments/aclt-multinode-admission'
AUTHORITY = 'experiments/aclt-authority-admission'
RIR_BUILD = 'experiments/aclt-rir-build-probe'
RIR_IO = 'experiments/aclt-rir-io-probe'
RIR_STATS = 'experiments/aclt-rir-stats-probe'
TASK_COMMITMENT = 'experiments/aclt-task-commitment'
TASK_AUTHORIZATION = 'experiments/aclt-task-authorization'
TASK_REPLAY = 'experiments/aclt-task-replay'
FUNDING_RESERVATION = 'experiments/aclt-funding-reservation'
FIXED_SETTLEMENT = 'experiments/aclt-fixed-settlement'
SETTLEMENT_RECOVERY = 'experiments/aclt-settlement-recovery'
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

def policy(root):
    value=json.loads((root/'DELIVERY-SCOPE.json').read_text())
    if value['schema']!='aclt.delivery-scope@1':raise ValueError('delivery policy version')
    return value

def skipped(relative,patterns):
    # Patterns are anchored to known generated locations, never arbitrary build/ names.
    parts=relative.parts
    if '__pycache__' in parts or '.git' in parts:return True
    return any(relative.full_match(p) for p in patterns if not p.startswith('**/'))

def delivery_files(root):
    cfg=policy(root);paths=[]
    for name in cfg['source_directories']:
        base=root/name
        if base.is_symlink() or (base.exists() and not base.is_dir()):raise ValueError('Unsafe source directory: '+name)
        for path in sorted(base.rglob('*')):
            relative=path.relative_to(root)
            if skipped(relative,cfg['excluded_generated_paths']):continue
            if path.is_symlink():raise ValueError('Symlink is not a delivery input: '+str(relative))
            if path.is_file():paths.append(path)
    for name in cfg['top_level_files']:
        path=root/name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=root and root in p.parents) or not path.is_file():raise ValueError('Missing/unsafe delivery input: '+name)
        paths.append(path)
    return sorted(set(paths))

def tracked_coverage(root,paths):
    # Do not accidentally use a parent checkout for an unpacked source directory.
    if not (root/'.git').exists() and not (root/'.git').is_symlink():return 'NOT_RUN_NO_CHECKOUT'
    r=git(root,'rev-parse','--show-toplevel')
    if Path(r.stdout.decode().strip()).resolve()!=root.resolve():
        raise ValueError('Git checkout root mismatch')
    names=set(git(root,'ls-files','-z').stdout.decode().rstrip('\0').split('\0'))
    covered={p.relative_to(root).as_posix() for p in paths}|set(policy(root)['tracked_exceptions'])
    present={n for n in names if (root/n).exists() or (root/n).is_symlink()}
    missing=present-covered
    if missing:raise ValueError('Unclassified tracked delivery paths: '+', '.join(sorted(missing)))
    return 'PASS'

def inventories(root):
    workflow = files(root, 'docs/workflow') + files(root, 'tests/workflow')
    workflow += [root / name for name in [
        '.aclt-flow/template.json', '.aclt-flow/.gitignore', 'scripts/aclt-flow.py',
        'scripts/package-singlehost.py', 'scripts/repository_files.py']]
    delivery=delivery_files(root)
    tracked_coverage(root,delivery)
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
