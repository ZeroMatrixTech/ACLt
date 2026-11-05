#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Explicit tested version scope; no downloads or claim of whole-toolchain pinning."""
import argparse
import json
import platform
import sqlite3
import subprocess
import sys
import unicodedata

def need(ok,message):
    if not ok:raise ValueError(message)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full',action='store_true');a=p.parse_args()
    try:
        need(sys.version_info[:2]==(3,14) and unicodedata.unidata_version=='16.0.0','tested Python 3.14 / Unicode 16.0.0 required')
        result=dict(python=platform.python_version(),unicode=unicodedata.unidata_version,sqlite=sqlite3.sqlite_version,scope='version guard; not content-pinned compiler/sysroot/OS')
        if a.full:
            for name,argv,prefix in [('rustc',['rustc','--version'],'rustc 1.93.1 '),('cargo',['cargo','--version'],'cargo 1.93.1 '),('openssl',['openssl','version'],'OpenSSL 3.5.'),('g++',['g++','-dumpfullversion'],'15.')]:
                text=subprocess.check_output(argv,text=True).strip();need(text.startswith(prefix),'outside tested tool scope: '+name+' '+text);result[name]=text
        print(json.dumps(dict(status='PASS',environment=result),indent=2))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:p.exit(1,str(exc)+'\n')
