#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only retained snapshot checker. Explicit external genesis pin required."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.formal_migration import s2,s2_evidence,s3_authority
from tools.verification_profile import codec as c
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path);p.add_argument('--snapshot',required=True,type=Path);p.add_argument('--expected-genesis',required=True);p.add_argument('--anchor',type=Path);p.add_argument('--s3b',action='store_true');a=p.parse_args()
    cfg=c.decode(a.config.read_bytes());c.need(s2.h(cfg).hex()==a.expected_genesis,'external genesis pin')
    verify=s3_authority.verify_snapshot if a.s3b else s2_evidence.verify
    print(json.dumps(verify(cfg,c.decode(a.snapshot.read_bytes()),c.decode(a.anchor.read_bytes()) if a.anchor else None),indent=2))
