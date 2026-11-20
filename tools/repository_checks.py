# SPDX-License-Identifier: Apache-2.0
"""Retained source records and current document checks."""
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

def need(ok,message):
    if not ok:raise ValueError(message)

def source_baseline(root,read_blob=None):
    """Read retained provenance; SHA pins are records, never admission gates."""
    record=json.loads((root/'docs/testing/SOURCE-BASELINE.json').read_text())
    return {'status':'DISABLED','pins':sum(len(record[k]) for k in ('main_source_hashes','files')),
            'source_verification':'DISABLED','sha_consistency':'DISABLED'}

def check_documents(root):
    claims=(root/'docs/06-research/claims-and-sources.md').read_text();ids=[]
    for line in claims.splitlines():
        if not line.startswith('| CLM-'):continue
        cols=[x.strip() for x in line.strip('|').split('|')];need(len(cols)==9,'claim columns')
        ids.append(cols[0]);need(cols[3].strip('`') in ('DERIVED','ASSUMPTION','HYPOTHESIS','—'),'unregistered ClaimQualifier')
        need(cols[6] in ('—','`P0`','`P1`','`P2`'),'priority column')
    need(ids and len(ids)==len(set(ids)),'duplicate Claim ID')
    decisions={}
    for p in (root/'docs/05-decisions').glob('ADR-*.md'):
        match=re.match(r'(ADR-\d{4})-',p.name);need(match is not None,'ADR filename')
        ident=match.group(1);need(ident not in decisions,'duplicate ADR ID '+ident);decisions[ident]=p
    links=0
    # Current Markdown prose links, excluding archived originals and code fences.
    for p in (root/'docs').rglob('*.md'):
        if 'codocs' in p.parts or 'workflow' in p.parts and 'example' in p.parts:continue
        fence=None
        for line in p.read_text().splitlines():
            stripped=line.lstrip()
            marker=re.match(r'(`{3,}|~{3,})',stripped)
            if marker:
                token=marker.group(1)[0]
                if fence is None:fence=token
                elif fence==token:fence=None
                continue
            if fence:continue
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',line):
                target=target.strip().split(' "',1)[0].strip('<>')
                if not target or target.startswith('#') or urlsplit(target).scheme:continue
                target=unquote(target.split('#',1)[0])
                need((p.parent/target).exists(),'broken prose link '+str(p.relative_to(root))+': '+target);links+=1
    return dict(status='PASS',claims=len(ids),decision_ids=len(decisions),local_prose_links=links,scope='Markdown paths, ADR identifiers, ClaimQualifier and Priority columns')
