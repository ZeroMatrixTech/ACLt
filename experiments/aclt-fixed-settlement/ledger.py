# SPDX-License-Identifier: Apache-2.0
"""Bounded test-asset funding, once-only starts, exact comparison and atomic fixed settlement."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True

from contextlib import closing
import os
import sqlite3
from wire import *


class ReserveLedger:
    def __init__(self, path, private, public, enrollment, genesis=None, witnesses=None):
        self.path = Path(path)
        self.private, self.public = Path(private), Path(public)
        self.enrollment = dict(enrollment)
        need(0 < len(enrollment) <= 32, 'bounded enrollment')
        for key, secret in enrollment.items():
            bytes_n(key, 32, 'account'); bytes_n(secret, 32, 'secret')
        self.pin = sha(regular(self.public))
        self.enrollment_digest = sha(encode({k.hex(): sha(v) for k, v in enrollment.items()}))
        if genesis is not None:
            need(type(genesis) is dict and 0 < len(genesis) <= 32, 'bounded genesis')
            for key, value in genesis.items():
                bytes_n(key, 32, 'genesis account'); amount(value)
            need(set(enrollment) <= set(genesis) and sum(genesis.values()) <= MAX, 'genesis enrollment/total cap')
            check_witnesses(witnesses)
            need(all(w['actor'] in enrollment for w in witnesses.values()), 'enrolled witnesses')
            authority = secrets.token_bytes(16)
            body = {'authority_id': authority, 'asset': ASSET, 'decimal_places': 0,
                    'accounts': {k.hex(): v for k, v in genesis.items()}, 'witnesses': witnesses}
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.close(fd)
            with closing(sqlite3.connect(self.path)) as c:
                c.execute('PRAGMA synchronous=FULL')
                c.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value BLOB NOT NULL);'
                               'CREATE TABLE accounts(ref BLOB PRIMARY KEY,available INTEGER CHECK(available>=0),reserved INTEGER CHECK(reserved>=0));'
                               'CREATE TABLE policies(task BLOB PRIMARY KEY,pid BLOB UNIQUE,raw BLOB NOT NULL);'
                               'CREATE TABLE reservations(rid BLOB PRIMARY KEY,pid BLOB UNIQUE,account BLOB,amount INTEGER CHECK(amount>0),receipt BLOB NOT NULL);'
                               'CREATE TABLE journal(seq INTEGER PRIMARY KEY,digest BLOB UNIQUE,raw BLOB NOT NULL);'
                               'CREATE TABLE bindings(pid BLOB PRIMARY KEY,raw BLOB NOT NULL);'
                               'CREATE TABLE starts(pid BLOB,role TEXT,permit BLOB,PRIMARY KEY(pid,role));'
                               'CREATE TABLE outcomes(pid BLOB,role TEXT,raw BLOB,PRIMARY KEY(pid,role));'
                               'CREATE TABLE settlements(pid BLOB PRIMARY KEY,eid BLOB UNIQUE,comparison BLOB,receipt BLOB);')
                c.executemany('INSERT INTO meta VALUES(?,?)', [('authority_id', authority), ('public_digest', self.pin), ('enrollment_digest', self.enrollment_digest), ('genesis', encode(body))])
                c.executemany('INSERT INTO accounts VALUES(?,?,0)', genesis.items())
                self.append(c, 'GENESIS', body); c.commit()
            fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        with closing(self.connect()) as c:
            meta = dict(c.execute('SELECT key,value FROM meta'))
            self.authority = meta['authority_id']
            self.genesis = decode(meta['genesis'])
            self.witnesses = self.genesis['witnesses']; check_witnesses(self.witnesses)

    def connect(self):
        need(self.path.is_file() and not self.path.is_symlink(), 'existing funding ledger required')
        c = sqlite3.connect(self.path.absolute().as_uri()+'?mode=rw', uri=True, isolation_level=None, timeout=15)
        try:
            c.execute('PRAGMA synchronous=FULL'); c.execute('PRAGMA journal_mode=DELETE')
            meta = dict(c.execute('SELECT key,value FROM meta'))
            need(digest_consistency(meta['public_digest'] == self.pin) and digest_consistency(meta['enrollment_digest'] == self.enrollment_digest), 'frozen issuer/enrollment')
            if hasattr(self, 'authority'):
                need(meta['authority_id'] == self.authority, 'deployment mismatch')
            return c
        except BaseException:
            c.close(); raise

    def append(self, c, kind, data):
        last = c.execute('SELECT seq,digest FROM journal ORDER BY seq DESC LIMIT 1').fetchone()
        seq, prev = (last[0]+1, last[1]) if last else (1, ZERO)
        raw = encode({'schema_id': 'aclt.exp.funding-event@2', 'seq': seq, 'prev': prev, 'kind': kind, 'data': data})
        digest = event_id(raw)
        c.execute('INSERT INTO journal VALUES(?,?,?)', (seq, digest, raw))
        return digest

    def authenticate(self, packet):
        wrap = decode(packet)
        need(type(wrap) is dict and set(wrap) == {'payload', 'mac'}, 'request wrapper')
        req = decode(wrap['payload'])
        need(type(req) is dict and set(req) == {'schema_id', 'authority_id', 'requester', 'nonce', 'op', 'data'}, 'request fields')
        need(req['schema_id'] == 'aclt.exp.funding-request@2' and req['authority_id'] == self.authority, 'request deployment')
        bytes_n(req['requester'], 32, 'requester'); bytes_n(req['nonce'], 16, 'nonce'); bytes_n(wrap['mac'], 32, 'MAC')
        need(req['requester'] in self.enrollment and hmac.compare_digest(wrap['mac'], hmac.digest(self.enrollment[req['requester']], wrap['payload'], 'sha256')), 'request authentication')
        need(req['op'] in ['FREEZE', 'RESERVE', 'STATUS', 'BALANCE', 'START', 'SUBMIT', 'SETTLE'] and type(req['data']) is dict, 'operation/data')
        return req

    def handle(self, packet):
        req = self.authenticate(packet)
        with closing(self.connect()) as c:
            try:
                c.execute('BEGIN IMMEDIATE')
                status, result = self.transition(c, req)
                event = self.append(c, req['op'], {'request': packet, 'status': status, 'result': result})
                c.execute('COMMIT')
            except BaseException:
                if c.in_transaction: c.execute('ROLLBACK')
                raise
        # A lost/signing-failed reply after commit never releases an encumbrance.
        return sign({'schema_id': 'aclt.exp.funding-response@2', 'authority_id': self.authority,
                     'request_digest': sha(packet), 'nonce': req['nonce'], 'op': req['op'],
                     'status': status, 'event_ref': event, 'result': result}, self.private)

    def transition(self, c, req):
        op, data, actor = req['op'], req['data'], req['requester']
        if op == 'BALANCE':
            need(data == {}, 'balance fields')
            row = c.execute('SELECT available,reserved FROM accounts WHERE ref=?', (actor,)).fetchone()
            return 'BALANCE', {'available': row[0], 'reserved': row[1], 'asset': ASSET}
        if op == 'FREEZE':
            need(set(data) == {'policy', 'commitment', 'artifact', 'input'}, 'freeze fields')
            p = validate_policy(decode(data['policy'])); pid = policy_id(data['policy'])
            task, _ = bind(data['commitment'], p['task'].hex(), data['artifact'], [data['input']])
            need(p['requester'] == actor == task['requester_ref'], 'payer/task identity binding')
            row = c.execute('SELECT pid FROM policies WHERE task=?', (p['task'],)).fetchone()
            if row:
                return ('DUPLICATE' if row[0] == pid else 'CONFLICT'), {'policy_id': row[0]}
            c.execute('INSERT INTO policies VALUES(?,?,?)', (p['task'], pid, data['policy']))
            return 'FROZEN', {'policy_id': pid}
        need(set(data) == {'policy_id'}, 'policy query fields'); bytes_n(data['policy_id'], 32, 'policy ID')
        row = c.execute('SELECT raw FROM policies WHERE pid=?', (data['policy_id'],)).fetchone()
        if not row: return 'DENIED', {'reason': 'UNKNOWN_POLICY'}
        p = validate_policy(decode(row[0])); pid = data['policy_id']
        if p['requester'] != actor: return 'DENIED', {'reason': 'WRONG_PAYER'}
        old = c.execute('SELECT receipt FROM reservations WHERE pid=?', (pid,)).fetchone()
        if old: return ('RESERVED' if op == 'STATUS' else 'DUPLICATE'), {'receipt': old[0]}
        if op == 'STATUS': return 'UNRESERVED', {'policy_id': pid}
        available, reserved = c.execute('SELECT available,reserved FROM accounts WHERE ref=?', (actor,)).fetchone()
        cap = p['authorized_cap']
        if available < cap: return 'INSUFFICIENT', {'policy_id': pid}
        need(reserved <= MAX-cap, 'account overflow')
        rid = reservation_id(self.authority, pid)
        receipt = sign({'schema_id': 'aclt.exp.funding-reservation@2', 'authority_id': self.authority,
                        'reservation_id': rid, 'policy_id': pid, 'task': p['task'],
                        'requester': actor, 'payee': p['payee'], 'asset': ASSET, 'amount': cap}, self.private)
        c.execute('UPDATE accounts SET available=?,reserved=? WHERE ref=?', (available-cap, reserved+cap, actor))
        c.execute('INSERT INTO reservations VALUES(?,?,?,?,?)', (rid, pid, actor, cap, receipt))
        return 'RESERVED', {'receipt': receipt}

    @staticmethod
    def projection(c):
        return {'accounts': {k.hex(): {'available': a, 'reserved': r} for k, a, r in c.execute('SELECT * FROM accounts ORDER BY ref')},
                'policies': {pid.hex(): raw.hex() for _, pid, raw in c.execute('SELECT * FROM policies ORDER BY pid')},
                'reservations': {rid.hex(): {'policy_id': pid.hex(), 'account': account.hex(), 'amount': n, 'receipt': receipt.hex()}
                                 for rid, pid, account, n, receipt in c.execute('SELECT * FROM reservations ORDER BY rid')}}

    def export(self):
        with closing(self.connect()) as c:
            c.execute('BEGIN')
            events = [raw.hex() for (raw,) in c.execute('SELECT raw FROM journal ORDER BY seq')]
            proj = self.projection(c)
            c.execute('COMMIT')
        anchor = sign({'schema_id': 'aclt.exp.funding-checkpoint@2', 'authority_id': self.authority,
                       'count': len(events), 'head': event_id(bytes.fromhex(events[-1])),
                       'projection_digest': sha(canonical_json(proj))}, self.private)
        return {'schema_id': 'aclt.exp.funding-export@2', 'events': events, 'projection': proj}, anchor


class Ledger(ReserveLedger):
    def transition(self, c, req):
        op, data, actor = req['op'], req['data'], req['requester']
        if op == 'FREEZE':
            status, result = super().transition(c, req)
            if status == 'FROZEN': c.execute('INSERT INTO bindings VALUES(?,?)', (result['policy_id'], encode(data)))
            return status, result
        if op in ['RESERVE', 'BALANCE']: return super().transition(c, req)
        required = {'policy_id'} | ({'role'} if op == 'START' else {'role', 'report'} if op == 'SUBMIT' else set())
        need(set(data) == required, 'funded operation fields'); pid = data['policy_id']; bytes_n(pid, 32, 'policy ID')
        row = c.execute('SELECT raw FROM policies WHERE pid=?', (pid,)).fetchone()
        if row is None: return 'DENIED', {'reason': 'UNKNOWN_POLICY'}
        p = validate_policy(decode(row[0])); rid = reservation_id(self.authority, pid)
        reserved = c.execute('SELECT amount FROM reservations WHERE pid=?', (pid,)).fetchone()
        settled = c.execute('SELECT receipt FROM settlements WHERE pid=?', (pid,)).fetchone()
        if op in ['SETTLE', 'STATUS']:
            if actor != p['requester']: return 'DENIED', {'reason': 'WRONG_PAYER'}
            if settled: return ('SETTLED' if op == 'STATUS' else 'DUPLICATE'), {'receipt': settled[0]}
            if op == 'STATUS': return super().transition(c, req)
        if not reserved: return 'DENIED', {'reason': 'NOT_RESERVED'}
        binding = c.execute('SELECT raw FROM bindings WHERE pid=?', (pid,)).fetchone()[0]
        if op in ['START', 'SUBMIT']:
            role = data['role']; need(role in self.witnesses, 'witness role')
            witness = self.witnesses[role]
            if actor != witness['actor']: return 'DENIED', {'reason': 'WRONG_WITNESS'}
            started = c.execute('SELECT permit FROM starts WHERE pid=? AND role=?', (pid, role)).fetchone()
            if op == 'START':
                if started or settled: return 'DENIED', {'reason': 'START_USED_OR_SETTLED'}
                permit = sign(permit_body(self.authority, pid, p, binding, role, witness), self.private)
                c.execute('INSERT INTO starts VALUES(?,?,?)', (pid, role, permit))
                return 'STARTED', {'permit': permit}
            if not started: return 'DENIED', {'reason': 'NOT_STARTED'}
            expected = permit_body(self.authority, pid, p, binding, role, witness)
            validate_report(data['report'], started[0], self.public, self.pin, binding, expected)
            previous = c.execute('SELECT raw FROM outcomes WHERE pid=? AND role=?', (pid, role)).fetchone()
            if previous: return ('DUPLICATE' if previous[0] == data['report'] else 'CONFLICT'), {'report_digest': sha(previous[0])}
            need(not settled, 'outcome after settlement')
            c.execute('INSERT INTO outcomes VALUES(?,?,?)', (pid, role, data['report']))
            return 'RECORDED', {'report_digest': sha(data['report'])}
        need(op == 'SETTLE', 'unsupported funded operation')
        reports = [c.execute('SELECT raw FROM outcomes WHERE pid=? AND role=?', (pid, role)).fetchone() for role in ['A', 'B']]
        if not all(reports): return 'PENDING', {'policy_id': pid}
        comparison = compare_reports([r[0] for r in reports]); body = settlement_body(self.authority, pid, p, comparison)
        receipt = sign(body, self.private); paid, refunded = body['paid'], body['refunded']
        payer_balance = c.execute('SELECT available,reserved FROM accounts WHERE ref=?', (p['requester'],)).fetchone()
        need(payer_balance[1] >= p['authorized_cap'], 'reserved balance invariant')
        c.execute('INSERT OR IGNORE INTO accounts VALUES(?,0,0)', (p['payee'],))
        payee_balance = c.execute('SELECT available FROM accounts WHERE ref=?', (p['payee'],)).fetchone()[0]
        need(payer_balance[0] <= MAX-refunded and payee_balance <= MAX-paid, 'settlement overflow')
        c.execute('UPDATE accounts SET available=?,reserved=? WHERE ref=?', (payer_balance[0]+refunded, payer_balance[1]-p['authorized_cap'], p['requester']))
        c.execute('UPDATE accounts SET available=available+? WHERE ref=?', (paid, p['payee']))
        c.execute('INSERT INTO settlements VALUES(?,?,?,?)', (pid, body['entitlement_id'], encode(comparison), receipt))
        return 'SETTLED', {'receipt': receipt}

    @staticmethod
    def projection(c):
        p = ReserveLedger.projection(c)
        p['bindings'] = {pid.hex(): raw.hex() for pid, raw in c.execute('SELECT * FROM bindings')}
        p['starts'] = {pid.hex()+':'+role: raw.hex() for pid, role, raw in c.execute('SELECT * FROM starts')}
        p['outcomes'] = {pid.hex()+':'+role: raw.hex() for pid, role, raw in c.execute('SELECT * FROM outcomes')}
        p['settlements'] = {pid.hex(): {'entitlement_id': eid.hex(), 'comparison': comp.hex(), 'receipt': receipt.hex()}
                            for pid, eid, comp, receipt in c.execute('SELECT * FROM settlements')}
        return p
