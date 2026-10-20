# SPDX-License-Identifier: Apache-2.0
"""Independent QEMU evidence checker: no imports from the implementation modules."""
import argparse
import collections
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checks = []
    raw_before={str(p.relative_to(args.evidence)):sha(p.read_bytes())
                for p in (args.evidence/'vms').glob('*/*.raw')}

    def ok(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        if not condition:
            (args.output/'offline-tests.json').write_text(json.dumps({'passed': False, 'checks': checks}, indent=2)+'\n')
            raise AssertionError(name)

    for vm in sorted((args.evidence/'vms').iterdir()):
        for disk in ['data', 'evidence']:
            dest = args.output/vm.name/disk
            dest.mkdir(parents=True)
            image = dest.parent/(disk+'.recovered.raw')
            shutil.copyfile(vm/(disk+'.raw'), image)
            recovery = subprocess.run(['e2fsck', '-p', str(image)], capture_output=True)
            (dest.parent/(disk+'.recovery.log')).write_bytes(recovery.stdout+recovery.stderr)
            ok('filesystem-recovered-'+vm.name+'-'+disk, recovery.returncode in (0, 1))
            dumped = subprocess.run(['debugfs', '-R', f'rdump / {dest}', str(image)], capture_output=True)
            ok('filesystem-extracted-'+vm.name+'-'+disk, dumped.returncode == 0)
    authority = args.output/'authority/data'
    config = json.loads((authority/'config.json').read_text())
    manifest = config['manifest']
    database = authority/'authority.sqlite'
    # Writable extracted copy permits SQLite hot-journal recovery; raw disks remain unchanged.
    c = sqlite3.connect(database)
    c.row_factory = sqlite3.Row
    ok('sqlite-integrity', c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
    meta = dict(c.execute('SELECT key,value FROM meta'))
    ok('manifest-digest', meta['config_digest'] == sha(canonical(manifest)))
    ok('public-key-digest', meta['public_digest'] == sha((authority/'authority.pub').read_bytes()))
    pins = json.loads((args.evidence/'client-pins.json').read_text())
    ok('trusted-identity-pins', all(meta[k] == pins[k] for k in ['authority_id','config_digest','public_digest']))
    slots = [dict(row) for row in c.execute('SELECT * FROM slots')]
    by = {(r['claim'], r['unit']): r for r in slots}
    ok('unique-authoritative-qualification', len(by) == len(slots))
    events = [dict(r) for r in c.execute('SELECT * FROM events ORDER BY seq')]
    reservations = collections.Counter((r['claim'],r['unit']) for r in events if r['op']=='reserve:reserved')
    ok('one-committed-grant-per-pair', len(reservations)==len(slots) and all(n==1 for n in reservations.values()))
    acceptance = collections.Counter((r['claim'],r['unit']) for r in events if r['op']=='submit:accepted')
    ok('one-committed-acceptance-per-pair', all(n==1 for n in acceptance.values()))
    expected = {}
    for task, contract in manifest['tasks'].items():
        values = contract['values'];chunk = contract['chunk']
        claim = sha(('ACLT-LOCAL-CLAIM-1\nstats-int-v1\n'+' '.join(map(str,values))).encode())
        text = ''
        for offset in range(0,len(values),chunk):
            group=values[offset:offset+chunk]
            text+=f'{offset//chunk} {offset} {len(group)} {sum(group)} {min(group)} {max(group)}\n'
        expected[task]=(claim,text)
    completed=collections.Counter();intentions=collections.Counter();wire_grants=collections.Counter();wire_count=0
    for node in ['node-a','node-b']:
        directory=args.output/node/'data/results'
        disk_config=json.loads((args.output/node/'data/config.json').read_text())
        ok('worker-authority-pins-'+node, all(disk_config['base'][k]==pins[k] for k in ['authority_id','config_digest','public_digest']))
        for wire in (args.output/node/'evidence').glob('wire-*.json'):
            data=json.loads(wire.read_text());request=data['request'];response=data['response']
            secret=manifest['keys'][request['key']]['secret']
            payload=dict(request);mac=payload.pop('mac')
            ok('wire-request-auth-'+wire.stem,hmac.compare_digest(mac,hmac.new(secret.encode(),canonical(payload),hashlib.sha256).hexdigest()))
            if set(response)!={'payload','signature'}:
                continue  # unsigned transport errors confer no authority; retained as failure evidence
            with tempfile.NamedTemporaryFile() as f:
                f.write(bytes.fromhex(response['signature']));f.flush()
                verified=subprocess.run(['openssl','dgst','-sha256','-verify',str(authority/'authority.pub'),
                                         '-signature',f.name],input=canonical(response['payload']),capture_output=True)
            p=response['payload'];claim,_=expected[request['task']];unit=manifest['keys'][request['key']]['unit']
            ok('wire-authority-signature-'+wire.stem,verified.returncode==0)
            ok('wire-response-binding-'+wire.stem,p['v']==2 and p['authority_id']==meta['authority_id']
               and p['config_digest']==meta['config_digest'] and p['request_digest']==sha(canonical(request))
               and p['nonce']==request['nonce'] and p['op']==request['op'] and p['key']==request['key']
               and p['boot']==request['boot'] and p['task']==request['task'] and p['claim']==claim and p['unit']==unit)
            if p['reply']['status']=='reserved':
                wire_grants[claim,unit]+=1
                ok('wire-grant-ticket-'+wire.stem,by[claim,unit]['ticket']==p['reply']['ticket'])
            if p['reply']['status'] in ['accepted','duplicate','conflict']:
                ok('wire-receipt-binding-'+wire.stem,by[claim,unit]['receipt']==p['reply']['receipt'])
            wire_count+=1
        for marker in directory.glob('*.started'):
            intent=json.loads(marker.read_text());claim,_=expected[intent['task']]
            slot=[r for r in slots if r['claim']==claim and r['ticket']==intent['ticket']]
            ok('launch-intent-has-committed-grant-'+node+'-'+marker.stem,len(slot)==1)
            intentions[claim,slot[0]['unit']]+=1
        for execution in directory.glob('*.execution.json'):
            data=json.loads(execution.read_text())
            packet_path=execution.with_name(execution.name.replace('.execution.json','.submit.json'))
            ok('completed-invocation-has-saved-packet-'+node+'-'+execution.stem,packet_path.exists())
            packet=json.loads(packet_path.read_text());mac=packet.pop('mac')
            key=manifest['keys'][packet['key']]
            ok('packet-hmac-'+node+'-'+execution.stem,
               hmac.compare_digest(mac,hmac.new(key['secret'].encode(),canonical(packet),hashlib.sha256).hexdigest()))
            claim,text=expected[packet['task']];pair=(claim,key['unit']);slot=by[pair]
            ok('worker-result-and-grant-'+node+'-'+execution.stem,
               data['rc']==0 and data['stdout_digest']==sha(text.encode()) and packet['rows']==text
               and packet['ticket']==slot['ticket'] and packet['boot']==slot['boot']==data['boot'])
            completed[pair]+=1
    ok('no-duplicate-completed-worker-invocations',all(n==1 for n in completed.values()))
    ok('no-duplicate-launch-intentions',all(n==1 for n in intentions.values()))
    ok('no-duplicate-signed-grants-observed',all(n==1 for n in wire_grants.values()))
    ok('every-observed-worker-start-has-signed-grant',all(wire_grants[pair]==1 for pair in intentions))
    ok('all-launch-intentions-have-completed-invocations',completed==intentions)
    for pair, slot in by.items():
        if slot['accepted_digest'] is not None:
            matching=[text for claim,text in expected.values() if claim==slot['claim']]
            ok('accepted-exact-result-'+str(pair),bool(matching) and slot['accepted_digest']==sha(matching[0].encode()))
            receipt=sha(canonical(['ACLT-EXPERIMENT-RECEIPT-2',meta['authority_id'],meta['config_digest'],
                                  slot['claim'],slot['unit'],slot['ticket'],slot['accepted_digest']]))
            ok('canonical-receipt-'+str(pair),receipt==slot['receipt'] and completed[pair]==1 and acceptance[pair]==1)
    final=json.loads((args.evidence/'final-audit.json').read_text())
    for task, units in final.items():
        for key, audit in units.items():
            claim,_=expected[task];slot=by.get((claim,manifest['keys'][key]['unit']))
            ok('audit-'+task+'-'+key,audit['reserved']==bool(slot)
               and audit['count']==int(bool(slot and slot['accepted_digest'] is not None))
               and audit['receipt']==(slot['receipt'] if slot else None)
               and audit['failed']==bool(slot and slot['failed'])
               and audit['conflict']==bool(slot and slot['conflict']))
    missing=args.output/'missing-authority/data/authority.sqlite'
    ok('missing-authority-not-recreated',not missing.exists())
    for name in ['gateway-primary','gateway-clone']:
        config=json.loads((args.output/name/'data/config.json').read_text())
        ok('gateway-has-no-worker-or-signing-credentials-'+name,set(config)<={'host','port','timeout'}
           and not list((args.output/name/'data').glob('*.key')))
    current=json.loads((args.evidence/'events.json').read_text())
    ok('all-recorded-assertions-pass',all(row.get('passed',True) for row in current))
    packed=next(e['evidence'] for e in current if e['name']=='guest-built')
    ok('initramfs-digest',sha((args.evidence/'guest.cpio').read_bytes())==packed['initramfs_sha256'])
    for name in ['protocol.py','authority.py','gateway.py','worker.py','server.py','vm_node.py']:
        with (args.evidence/'guest.cpio').open('rb') as archive:
            unpacked=subprocess.run(['cpio','-i','--to-stdout','experiment/'+name],stdin=archive,capture_output=True,check=True).stdout
        ok('deployed-source-'+name,sha(unpacked)==packed['sources'][name]
           and unpacked==(Path(__file__).resolve().parent/name).read_bytes())
    faults=json.loads((args.evidence/'faults.json').read_text())
    random_coverage={}
    for fault in faults:
        interrupted=fault['interrupted']
        reply=interrupted.get('reply',interrupted)
        if reply.get('status') in ['accepted','duplicate']:
            ok('acknowledged-acceptance-survived-cut-'+fault['task'],fault['state']['count']==1
               and fault['state']['receipt']==reply['receipt'])
        if interrupted.get('computed') is True:
            ok('executed-work-keeps-reservation-'+fault['task'],fault['state']['reserved'])
    for op in ['reserve','submit']:
        selected=[f for f in faults if f['task'].startswith('random-'+op+'-')]
        random_coverage[op]={'samples':len(selected),'committed_after_reboot':sum(f['observed_commit'] for f in selected),
                             'not_committed_after_reboot':sum(not f['observed_commit'] for f in selected),
                             'internal_SQLite_windows':'not individually identified; deterministic stage cuts are reported separately'}
    boot_counts={}
    for vm in ['authority','gateway-primary','gateway-clone','node-a','node-b']:
        boot_ids=[json.loads(p.read_text())['boot'] for p in (args.output/vm/'evidence').glob('boot-*.json')]
        boot_counts[vm]=len(boot_ids)
        ok('fresh-boot-records-'+vm,len(boot_ids)>0 and len(set(boot_ids))==len(boot_ids))
    report={'passed':True,'checks':len(checks),'authoritative_grants':len(slots),
            'accepted_contributions':sum(r['accepted_digest'] is not None for r in slots),
            'launch_intentions':sum(intentions.values()),'completed_worker_invocations':sum(completed.values()),
            'verified_wire_responses':wire_count,
            'random_coverage':random_coverage,
            'boots':boot_counts,'tests':checks}
    ok('raw-disks-unchanged',all(sha((args.evidence/name).read_bytes())==digest for name,digest in raw_before.items()))
    report['checks']=len(checks)
    (args.output/'offline-tests.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='tests'},indent=2))


if __name__=='__main__':
    main()
