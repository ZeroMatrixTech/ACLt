"""One delivery inventory for manifests and packaging (Python standard library).

The delivery scope and the digest policy both live in ``DELIVERY-SCOPE.json``;
nothing here hard-codes which tracked paths are pinned.  Every delivery input is
classified by the ordered rules in that file:

1. ``tracked_exceptions``;
2. ``never_digest_patterns`` (documentation is delivered but never pinned);
3. ``digest_patterns`` (code, tests, configuration, evidence and fixtures);
4. ``delivery_only_patterns`` (delivered, not pinned);
5. any other delivered path fails closed.

The two root manifests list only the ``DIGEST`` set.  The archive still carries
every delivery file, so a missing unpinned file is caught by package
verification rather than by the manifest.
"""
from pathlib import Path
import hashlib
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.git_sources import git

EXPERIMENT = 'experiments/aclt-minimal-verifier-state3'
MULTINODE = 'experiments/aclt-multinode-admission'
AUTHORITY = 'experiments/aclt-authority-admission'
EXCLUDE = {'target', 'build', '.toolchain', '__pycache__', '.git', 'artifacts', 'dist'}

DIGEST = 'DIGEST'
DELIVERY_ONLY = 'DELIVERY_ONLY'
EXCEPTION = 'EXCEPTION'
CLASSIFICATIONS = (DIGEST, DELIVERY_ONLY, EXCEPTION)
# Ordered rule keys and the classification each one yields.
RULES = (('never_digest_patterns', DELIVERY_ONLY),
         ('digest_patterns', DIGEST),
         ('delivery_only_patterns', DELIVERY_ONLY))

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
    value = json.loads((root / 'DELIVERY-SCOPE.json').read_text())
    if value.get('schema') != 'aclt.delivery-scope@2':
        raise ValueError('delivery policy version')
    if value.get('classification_order') != ['tracked_exceptions'] + [key for key, _ in RULES]:
        raise ValueError('delivery policy classification order')
    if not isinstance(value.get('tracked_exceptions'), dict):
        raise ValueError('delivery policy tracked_exceptions')
    for key, _ in RULES:
        patterns = value.get(key)
        if not isinstance(patterns, list) or not patterns:
            raise ValueError('delivery policy patterns: ' + key)
        if not all(isinstance(pattern, str) and pattern for pattern in patterns):
            raise ValueError('delivery policy patterns: ' + key)
    return value

def classify(relative, value):
    """Return the single classification of a delivery path, or fail closed."""
    name = relative.as_posix()
    if name in value['tracked_exceptions']:
        return EXCEPTION
    for key, result in RULES:
        for pattern in value[key]:
            if relative.full_match(pattern):
                return result
    raise ValueError('Unclassified delivery path: ' + name)

def skipped(relative,patterns):
    # Patterns are anchored to known generated locations, never arbitrary build/ names.
    parts=relative.parts
    if '__pycache__' in parts or '.git' in parts:return True
    return any(relative.full_match(p) for p in patterns if not p.startswith('**/'))

def delivery_files(root, value=None):
    value=policy(root) if value is None else value;paths=[]
    for name in value['source_directories']:
        base=root/name
        if base.is_symlink() or (base.exists() and not base.is_dir()):raise ValueError('Unsafe source directory: '+name)
        for path in sorted(base.rglob('*')):
            relative=path.relative_to(root)
            if skipped(relative,value['excluded_generated_paths']):continue
            if path.is_symlink():raise ValueError('Symlink is not a delivery input: '+str(relative))
            if path.is_file():paths.append(path)
    for name in value['top_level_files']:
        path=root/name
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=root and root in p.parents) or not path.is_file():raise ValueError('Missing/unsafe delivery input: '+name)
        paths.append(path)
    return sorted(set(paths))

def classified_paths(root, value=None):
    """Return the policy and one classification per delivery path."""
    value=policy(root) if value is None else value
    paths=delivery_files(root,value)
    kinds={}
    for path in paths:
        kind=classify(path.relative_to(root),value)
        if kind not in CLASSIFICATIONS:raise ValueError('Unknown delivery classification: '+str(kind))
        kinds[path]=kind
    return value,kinds

def digest_files(root):
    """The pinned delivery set, which is exactly what the root manifests list."""
    _,kinds=classified_paths(root)
    return [path for path,kind in kinds.items() if kind==DIGEST]

def in_delivery_scope(name,value):
    """True when the policy treats a tracked path as a delivery input."""
    if name in value['tracked_exceptions'] or name in value['top_level_files']:
        return True
    relative=Path(name)
    for directory in value['source_directories']:
        if name==directory or name.startswith(directory+'/'):
            return not skipped(relative,value['excluded_generated_paths'])
    return False

def tracked_coverage(root,paths=None):
    # Do not accidentally use a parent checkout for an unpacked source directory.
    if not (root/'.git').exists() and not (root/'.git').is_symlink():return 'NOT_RUN_NO_CHECKOUT'
    r=git(root,'rev-parse','--show-toplevel')
    if Path(r.stdout.decode().strip()).resolve()!=root.resolve():
        raise ValueError('Git checkout root mismatch')
    names=set(git(root,'ls-files','-z').stdout.decode().rstrip('\0').split('\0'))
    value=policy(root)
    exceptions=set(value['tracked_exceptions'])
    expected={n for n in names if in_delivery_scope(n,value)}
    outside=sorted(names-expected)
    if outside:raise ValueError('Tracked paths outside delivery scope: '+', '.join(outside))
    # A checkout must not silently package an incomplete delivery set: every
    # tracked delivery file has to exist in the working tree.  A file removed
    # through Git leaves the index, so it is no longer required.
    present={n for n in names if (root/n).exists() or (root/n).is_symlink()}
    absent=sorted(expected-present-exceptions)
    if absent:raise ValueError('Tracked delivery files missing from the working tree: '+', '.join(absent))
    delivered={p.relative_to(root).as_posix() for p in (delivery_files(root,value) if paths is None else paths)}
    uncovered=sorted((present&expected-exceptions)-delivered)
    if uncovered:raise ValueError('Tracked delivery paths outside the provided coverage: '+', '.join(uncovered))
    # Every tracked delivery path must fall into exactly one ordered rule.
    unclassified=[]
    for name in sorted(present&expected&delivered):
        try:classify(Path(name),value)
        except ValueError:unclassified.append(name)
    if unclassified:raise ValueError('Unclassified tracked delivery paths: '+', '.join(unclassified))
    return 'PASS'

def workflow_inputs(root):
    paths = files(root, 'docs/workflow') + files(root, 'tests/workflow')
    return paths + [root / name for name in [
        '.aclt-flow/template.json', '.aclt-flow/.gitignore', 'scripts/aclt-flow.py',
        'scripts/package-singlehost.py', 'scripts/repository_files.py']]

def inventories(root):
    value=policy(root)
    delivery=delivery_files(root,value)
    kinds={path:classify(path.relative_to(root),value) for path in delivery}
    workflow=workflow_inputs(root)
    outside=sorted(path.relative_to(root).as_posix() for path in workflow if path not in kinds)
    if outside:raise ValueError('Workflow inputs outside delivery scope: '+', '.join(outside))
    tracked_coverage(root,delivery)
    return {
        EXPERIMENT + '/SHA256SUMS': (root / EXPERIMENT, [
            p for p in files(root, EXPERIMENT) if p.name != 'SHA256SUMS']),
        MULTINODE + '/SHA256SUMS': (root / MULTINODE, [
            p for p in files(root, MULTINODE) if p.name != 'SHA256SUMS']),
        AUTHORITY + '/SHA256SUMS': (root / AUTHORITY, [
            p for p in files(root, AUTHORITY) if p.name != 'SHA256SUMS']),
        'WORKFLOW-SHA256SUMS': (root, [p for p in workflow if kinds[p] == DIGEST]),
        'SINGLEHOST-SHA256SUMS': (root, [p for p in delivery if kinds[p] == DIGEST]),
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
