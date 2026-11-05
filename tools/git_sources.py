# SPDX-License-Identifier: Apache-2.0
"""Read explicitly selected local repositories without persistent Git config changes."""
from pathlib import Path
import subprocess


def git(repository, *arguments, check=True):
    repository = Path(repository).resolve(strict=True)
    result = subprocess.run(
        ['git', '-c', 'safe.directory=' + str(repository), '-C', str(repository), *arguments],
        capture_output=True)
    if check and result.returncode:
        raise ValueError('Git failed (exit %d) in %s: %s\n%s' % (
            result.returncode, repository, ' '.join(arguments),
            result.stderr.decode('utf-8', errors='replace').strip()))
    return result


def read_blob(repository, revision, path):
    return git(repository, 'show', revision + ':' + path).stdout
