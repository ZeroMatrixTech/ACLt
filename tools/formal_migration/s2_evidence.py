# SPDX-License-Identifier: Apache-2.0
"""Public offline snapshot replay; no role/issuer private key needed to verify.

The genesis pin and an independently saved checkpoint must come from outside the
bundle. A self-contained signed bundle cannot establish its own trust/freshness.
"""
from contextlib import closing
from tools.formal_migration import s2
from tools.verification_profile import codec as c

def export(ledger):
    with closing(ledger.connect()) as db:
        db.execute('BEGIN');genesis,state=db.execute('SELECT genesis,state FROM meta').fetchone();rows=list(db.execute('SELECT seq,raw,digest FROM events ORDER BY seq'))
        c.need([r[0] for r in rows]==list(range(1,len(rows)+1)),'snapshot SQL sequence')
        checkpoint=dict(schema=s2.SCHEMA,genesis=genesis,seq=len(rows),head=rows[-1][2] if rows else s2.ZERO,state_digest=s2.h(c.decode(state)))
        pack=dict(schema=s2.SCHEMA,checkpoint=checkpoint,signature=s2.sign(ledger.private,'SNAPSHOT',checkpoint),state=state,events=[r[1] for r in rows]);db.rollback()
    verify(ledger.cfg,pack,transition=ledger.transition);return pack

def verify(cfg,pack,anchor=None,*,transition=s2.Ledger.transition,capture=()):
    """Optionally retain pre-event state and result at requested sequence numbers.

    Captures are returned only after the signature, entire chain, final projection
    and supplied anchor have been verified.
    """
    s2.config_check(cfg);s2.fields(pack,{'schema','checkpoint','signature','state','events'})
    cp=pack['checkpoint'];s2.fields(cp,{'schema','genesis','seq','head','state_digest'})
    c.need(pack['schema']==cp['schema']==s2.SCHEMA and cp['genesis']==s2.h(cfg),'snapshot context')
    s2.verify_signature(cfg['issuer_der'],'SNAPSHOT',cp,pack['signature'])
    c.need(type(pack['events']) is list and len(pack['events'])==cp['seq']<=256,'snapshot count')
    c.need(all(type(seq) is int and 1 <= seq <= cp['seq'] for seq in capture), 'capture sequence')
    captures = {}
    state=s2.initial(cfg);head=s2.ZERO;seen={0:(head,s2.h(state))};prefix=[]
    for seq,raw in enumerate(pack['events'],1):
        event=c.decode(raw);s2.fields(event,{'schema','genesis','seq','prev','parents','now','request','state_digest','result_digest'})
        c.need(event['schema']==s2.SCHEMA and event['genesis']==s2.h(cfg) and event['seq']==seq and event['prev']==head and event['parents']==([] if seq==1 else [head]),'snapshot chain')
        nxt,result,_=transition(cfg,state,event['request'],event['now'],prefix)
        prefix.append(raw)
        c.need(s2.h(nxt)==event['state_digest'] and s2.h(result)==event['result_digest'],'snapshot replay digest')
        if seq in capture:
            captures[seq] = (c.encode(state), c.encode(result))
        state=nxt;head=s2.h(event);seen[seq]=(head,s2.h(state))
    c.need(c.encode(state)==pack['state'] and head==cp['head'] and s2.h(state)==cp['state_digest'],'snapshot projection')
    if anchor is not None:
        c.need(anchor['schema']==s2.SCHEMA and anchor['genesis']==s2.h(cfg),'anchor genesis')
        c.need(seen.get(anchor['seq'])==(anchor['head'],anchor['state_digest']),'anchor consistency')
    report = dict(status='PASS',events=cp['seq'],head=head.hex(),state_digest=s2.h(state).hex(),
                  funds_held=state['held'],official_admission=False)
    if capture:
        report['captures'] = captures
    return report
