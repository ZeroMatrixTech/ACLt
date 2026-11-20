#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record the local tool versions used for this execution."""
import argparse
import json
import platform
import sqlite3
import subprocess
import unicodedata

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full',action='store_true');a=p.parse_args()
    try:
        result=dict(python=platform.python_version(),unicode=unicodedata.unidata_version,sqlite=sqlite3.sqlite_version,scope='execution environment record; fixed version gate DISABLED')
        if a.full:
            for name,argv in [('rustc',['rustc','--version']),('cargo',['cargo','--version']),('openssl',['openssl','version']),('g++',['g++','-dumpfullversion'])]:
                result[name]=subprocess.check_output(argv,text=True).strip()
        print(json.dumps(dict(status='RECORDED',fixed_version_gate='DISABLED',environment=result),indent=2))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:p.exit(1,str(exc)+'\n')
