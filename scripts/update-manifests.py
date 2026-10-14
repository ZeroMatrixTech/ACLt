#!/usr/bin/env python3
"""Refresh intentional delivery changes, or check without modifying files."""
import argparse
from pathlib import Path
from repository_files import EXPERIMENT, refresh, verify

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate without writing')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check:
        errors = verify(root)
        if errors:
            parser.exit(1, 'STALE manifests: ' + ', '.join(errors) + '\nRun make manifests after reviewing the changes.\n')
        print('PASS: delivery manifests match the current inventory')
    else:
        refresh(root)
        print('Updated delivery manifests; review their diff before delivery')

if __name__ == '__main__':
    main()
