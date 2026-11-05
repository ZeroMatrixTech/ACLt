# SPDX-License-Identifier: Apache-2.0
"""Bounded source-evidence and live-document checks, not protocol conformance."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit

def need(ok,message):
    if not ok:raise ValueError(message)

def source_baseline(root,read_blob=None):
    original=root/'docs/testing/SOURCE-BASELINE.json';record=json.loads(original.read_text());correction=json.loads((root/'docs/testing/SOURCE-BASELINE-correction-20261105.json').read_text())
    need(correction['schema']=='aclt.evidence.source-baseline-correction@1' and correction['gate_changes'] is False,'correction scope')
    need(correction['original_record']=='docs/testing/SOURCE-BASELINE.json' and correction['original_record_sha256']==hashlib.sha256(original.read_bytes()).hexdigest(),'original evidence bytes changed')
    need(correction['original_final_repository_head']==record['final_repository_head'] and correction['original_final_repository_branch']==record['final_repository_branch'],'historical head replaced')
    need(correction['original_head_status']=='UNRESOLVED_IN_RETAINED_HISTORY','unresolved provenance must stay explicit')
    need(correction['main_group_revision']==record['main'],'wrong main group')
    count=0
    for group,n in correction['group_counts'].items():
        need(group in ('main_source_hashes','files') and len(record[group])==n,'pin group count')
        for name,want in record[group].items():
            path=Path(name);need(not path.is_absolute() and '..' not in path.parts and re.fullmatch('[0-9a-f]{64}',want),'unsafe source pin')
            if read_blob is not None:
                data=read_blob(correction['verified_pinned_files_revision'],name);need(hashlib.sha256(data).hexdigest()==want,'mapped file mismatch: '+name)
                if group=='main_source_hashes':need(hashlib.sha256(read_blob(record['main'],name)).hexdigest()==want,'main group mismatch: '+name)
            count+=1
    need(set(correction['group_counts'])=={'main_source_hashes','files'} and count==43,'all baseline groups required')
    return {'status':'PASS','pins':count,'source_verification':'PASS' if read_blob else 'NOT_RUN','original_head_status':correction['original_head_status']}

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
    return dict(status='PASS',claims=len(ids),decision_ids=len(decisions),local_prose_links=links,scope='live Markdown paths, root ADR uniqueness, ClaimQualifier/Priority columns; not all prose semantics or historical audit completeness')
