# SPDX-License-Identifier: Apache-2.0
"""Generate Unicode 16.0 canonical data, not normalization code (Python stdlib)."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import unicodedata as u
from pathlib import Path
assert u.unidata_version == '16.0.0', 'use Unicode 16.0.0 generator'
decomp = []
combining = []
compose = []
for n in range(1114112):
    c = chr(n)
    d = u.decomposition(c)
    if d and (not d.startswith('<')):
        parts = [int(x, 16) for x in d.split()]
        decomp.append((n, parts))
        if len(parts) == 2 and u.normalize('NFC', ''.join(map(chr, parts))) == c:
            compose.append((parts[0], parts[1], n))
    if u.combining(c):
        combining.append((n, u.combining(c)))
s = '// SPDX-License-Identifier: Unicode-3.0\n// Generated Unicode 16.0.0 canonical normalization data. See generate_unicode.py and UNICODE-LICENSE.txt.\n'
s += 'pub const DECOMP: &[(u32, &[u32])] = &[\n' + ''.join((f'({n}, &{p}),\n' for n, p in decomp)) + '];\n'
s += 'pub const CCC: &[(u32, u8)] = &[\n' + ''.join((f'({n}, {c}),\n' for n, c in combining)) + '];\n'
s += 'pub const COMPOSE: &[(u32, u32, u32)] = &[\n' + ''.join((f'({a}, {b}, {c}),\n' for a, b, c in sorted(compose))) + '];\n'
Path(__file__).with_name('unicode_data.rs').write_text(s)
