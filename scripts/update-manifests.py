#!/usr/bin/env python3
"""SHA manifest generation and consistency checks are disabled by the maintainer."""
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.parse_args()
    print(json.dumps(dict(status='DISABLED', check='sha-manifests',
                          reason='maintainer decision 2026-11-19')))
