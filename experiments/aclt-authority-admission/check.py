# SPDX-License-Identifier: Apache-2.0
"""R01-R12 local checks: real framing/relay/signatures plus durable process cuts."""
import argparse
import concurrent.futures
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from authority import Authority
from gateway import Gateway
from protocol import (canonical, claim, create_keys, digest, envelope, exchange,
                      rows, sign_request, verified_reply)
from server import server
from worker import Worker


def manifest():
    tasks = {name: {'values': [3+i, -1, 8, 0, -7, 12], 'chunk': 4, 'units': ['A', 'B']}
             for i, name in enumerate(['normal', 'other', 'invalid'])}
    tasks['alias'] = tasks['normal']
    return {'keys': {'a': {'unit': 'A', 'secret': 'v2-test-only-a'},
                     'a-alias': {'unit': 'A', 'secret': 'v2-test-only-alias'},
                     'b': {'unit': 'B', 'secret': 'v2-test-only-b'},
                     'c': {'unit': 'C', 'secret': 'v2-test-only-c'}}, 'tasks': tasks}


def client_config(authority, key='a'):
    return {'authority_id': authority.authority_id, 'config_digest': authority.config_digest,
            'public_digest': authority.public_digest, 'key': key,
            **authority.manifest['keys'][key], 'tasks': authority.manifest['tasks']}


BOOT = '00000000-0000-0000-0000-000000000000'


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.private, cls.public = create_keys(cls.keys.name)
        cls.worker_executable = Path(os.environ.get('ACLT_AUTHORITY_WORKER', str(ROOT.parent / 'aclt-minimal-verifier-state3/build/worker')))
        if not cls.worker_executable.is_file():
            raise RuntimeError('build state3 worker before running checks')

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.authority = Authority(manifest(), self.path/'authority.sqlite', self.private, self.public, True)
        self.config = client_config(self.authority)
        self.tcp = server(self.authority, '127.0.0.1', 0)
        self.thread = threading.Thread(target=self.tcp.serve_forever, daemon=True)
        self.thread.start()
        self.gateway = Gateway('127.0.0.1', self.tcp.server_address[1])

    def tearDown(self):
        self.tcp.shutdown()
        self.tcp.server_close()
        self.thread.join()
        self.temp.cleanup()

    def node(self, name='node', config=None, transport=None):
        return Worker(self.path/name, config or self.config, self.public, self.worker_executable,
                      transport or self.gateway.handle, boot=BOOT)

    def send(self, op, task='normal', config=None, gateway=None, **extra):
        cfg = config or self.config
        msg = envelope(cfg, op, BOOT, task=task, **extra)
        return verified_reply((gateway or self.gateway).handle(msg), self.public, msg, cfg)

    def test_R01_normal_and_audit_no_recompute(self):
        node = self.node()
        result = node.compute('normal')
        self.assertEqual(result['reply']['status'], 'accepted')
        before = {p.name: p.read_bytes() for p in node.directory.iterdir()}
        self.assertEqual(node.audit('normal')['count'], 1)
        self.assertEqual(node.replay('normal')['receipt'], result['reply']['receipt'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in node.directory.iterdir()})
        self.assertEqual(len(list(node.directory.glob('*.execution.json'))), 1)
        with self.assertRaises(FileExistsError):
            self.node().compute('normal')

    def test_R02_gateway_rollback_after_reserve(self):
        snapshot = {'host': self.gateway.host, 'port': self.gateway.port}
        self.assertEqual(self.send('reserve')['status'], 'reserved')
        restored = Gateway(**snapshot)
        result = self.node('fresh-node', transport=restored.handle).compute('normal')
        self.assertEqual(result['reservation']['status'], 'consumed')
        self.assertFalse(list((self.path/'fresh-node').glob('*.started')))

    def test_R03_gateway_rollback_after_acceptance(self):
        node = self.node()
        first = node.compute('normal')
        node.transport = Gateway(self.gateway.host, self.gateway.port).handle
        self.assertEqual(node.replay('normal'), {'status': 'duplicate', 'receipt': first['reply']['receipt']})

    def test_R04_cloned_gateways_parallel_same_unit(self):
        nodes = [self.node('a'), self.node('b', transport=Gateway(self.gateway.host, self.gateway.port).handle)]
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda n: n.compute('normal'), nodes))
        self.assertEqual(sum(r['computed'] for r in results), 1)
        self.assertEqual(self.send('audit')['count'], 1)
        self.assertEqual(sum(len(list(n.directory.glob('*.execution.json'))) for n in nodes), 1)

    def test_R05_duplicate_and_conflict_across_gateways(self):
        node = self.node()
        first = node.compute('normal')['reply']
        saved = json.loads(next(node.directory.glob('*.submit.json')).read_text())
        saved['rows'] = 'WRONG\n'
        saved.pop('mac')
        saved = sign_request(saved, self.config['secret'])
        reply = self.gateway.handle(saved)
        self.assertEqual(verified_reply(reply, self.public, saved, self.config),
                         {'status': 'conflict', 'receipt': first['receipt']})
        self.assertEqual(node.replay('normal')['receipt'], first['receipt'])
        self.assertTrue(node.audit('normal')['conflict'])

    def test_R06_lost_reserve_reply_sacrifices_availability(self):
        def lost(message):
            self.gateway.handle(message)
            raise ConnectionError('injected lost reply')
        node = self.node(transport=lost)
        with self.assertRaises(ConnectionError):
            node.compute('normal')
        self.assertEqual(self.send('reserve')['status'], 'consumed')
        self.assertFalse(list(node.directory.glob('*.started')))
        with self.assertRaises(FileExistsError):
            self.node().compute('normal')

    def test_R07_lost_submit_reply_replays_same_packet(self):
        node = self.node()
        node.compute('normal', prepare_only=True)
        packet = next(node.directory.glob('*.submit.json'))
        before = packet.read_bytes()
        def lost(message):
            self.gateway.handle(message)
            raise ConnectionError('injected lost acknowledgement')
        node.transport = lost
        with self.assertRaises(ConnectionError):
            node.replay('normal')
        receipt = self.send('audit')['receipt']
        node.transport = self.gateway.handle
        self.assertEqual(node.replay('normal'), {'status': 'duplicate', 'receipt': receipt})
        self.assertEqual(packet.read_bytes(), before)

    def test_R08_authority_unreachable_no_offline_grant(self):
        unavailable = Gateway('127.0.0.1', 1, timeout=.1)
        node = self.node(transport=unavailable.handle)
        with self.assertRaises(OSError):
            node.compute('normal')
        self.assertFalse(list(node.directory.glob('*.started')))
        self.assertFalse(self.send('audit')['reserved'])

    def test_R08_pending_submit_survives_disconnection(self):
        node = self.node()
        node.compute('normal', prepare_only=True)
        node.transport = Gateway('127.0.0.1', 1, timeout=.1).handle
        with self.assertRaises(OSError):
            node.replay('normal')
        node.transport = self.gateway.handle
        self.assertEqual(node.replay('normal')['status'], 'accepted')
        self.assertEqual(len(list(node.directory.glob('*.started'))), 1)

    def test_R09_transaction_before_commit_rolls_back(self):
        def fail(stage):
            if stage == 'reserve-before-commit':
                raise OSError('injected storage failure')
        self.authority.hook = fail
        with self.assertRaises(ValueError):
            self.send('reserve')
        self.authority.hook = None
        self.assertFalse(self.send('audit')['reserved'])
        self.assertEqual(self.send('reserve')['status'], 'reserved')

    def test_R09_after_commit_failure_never_refunds(self):
        def fail(stage):
            if stage == 'reserve-after-commit':
                raise OSError('injected post-commit failure')
        self.authority.hook = fail
        with self.assertRaises(ValueError):
            self.send('reserve')
        self.authority.hook = None
        self.assertEqual(self.send('reserve')['status'], 'consumed')

    def test_R10_gateway_has_no_local_ledger_or_cache(self):
        node = self.node()
        receipt = node.compute('normal')['reply']['receipt']
        fresh = Gateway(self.gateway.host, self.gateway.port)
        self.assertEqual(set(vars(fresh)), {'host', 'port', 'timeout'})
        self.assertEqual(self.send('audit', gateway=fresh)['receipt'], receipt)
        self.assertEqual(self.send('reserve', gateway=fresh)['status'], 'consumed')

    def test_R10_authority_missing_after_open_never_recreated(self):
        self.authority.path.unlink()
        with self.assertRaises(ValueError):
            self.send('reserve')
        self.assertFalse(self.authority.path.exists())
        with self.assertRaises(FileNotFoundError):
            Authority(manifest(), self.authority.path, self.private, self.public)

    def test_R10_corrupt_authority_fails_closed(self):
        self.authority.path.write_bytes(b'not a ledger')
        with self.assertRaises(ValueError):
            self.send('reserve')
        with self.assertRaises(sqlite3.DatabaseError):
            Authority(manifest(), self.authority.path, self.private, self.public)

    def test_R10_reinitialize_and_symlink_refused(self):
        with self.assertRaises(FileExistsError):
            Authority(manifest(), self.authority.path, self.private, self.public, True)
        link = self.path/'link'
        link.symlink_to(self.authority.path)
        with self.assertRaises(ValueError):
            Authority(manifest(), link, self.private, self.public)

    def test_R11_task_and_key_alias_share_qualification(self):
        self.send('reserve')
        alias = client_config(self.authority, 'a-alias')
        self.assertEqual(self.send('reserve', task='alias', config=alias)['status'], 'consumed')

    def test_R11_alias_order_is_irrelevant_but_changed_contract_refused(self):
        m = copy.deepcopy(manifest())
        m['tasks']['alias'] = copy.deepcopy(m['tasks']['alias'])
        m['tasks']['alias']['units'] = ['B', 'A']
        a = Authority(m, self.path/'reordered.sqlite', self.private, self.public, True)
        cfg = client_config(a)
        msg = envelope(cfg, 'reserve', BOOT, task='normal')
        self.assertEqual(verified_reply(a.handle(msg), self.public, msg, cfg)['status'], 'reserved')
        msg = envelope(cfg, 'reserve', BOOT, task='alias')
        self.assertEqual(verified_reply(a.handle(msg), self.public, msg, cfg)['status'], 'consumed')
        m['tasks']['alias']['chunk'] = 2
        with self.assertRaises(ValueError):
            Authority(m, self.path/'ambiguous.sqlite', self.private, self.public, True)
        self.assertFalse((self.path/'ambiguous.sqlite').exists())

    def test_R11_authority_and_config_binding(self):
        for field in ['authority_id', 'config_digest']:
            wrong = dict(self.config)
            wrong[field] = '0' * len(wrong[field])
            with self.assertRaises(ValueError):
                self.send('reserve', config=wrong)
        self.assertFalse(self.send('audit')['reserved'])

    def test_R11_signed_response_cannot_be_reused_for_another_request(self):
        first = envelope(self.config, 'reserve', BOOT, task='normal')
        reply = self.gateway.handle(first)
        new = envelope(self.config, 'reserve', BOOT, task='normal')
        with self.assertRaises(ValueError):
            verified_reply(reply, self.public, new, self.config)
        reply['payload']['reply']['ticket'] = '0'*32
        with self.assertRaises(ValueError):
            verified_reply(reply, self.public, first, self.config)

    def test_R11_old_key_version_and_unsigned_reply_refused(self):
        msg = envelope(self.config, 'reserve', BOOT, task='normal')
        bad = dict(msg);bad.pop('mac');bad['v'] = 1
        with self.assertRaises(ValueError):
            verified_reply(self.gateway.handle(sign_request(bad, self.config['secret'])), self.public, msg, self.config)
        bad['v'] = 2
        with self.assertRaises(ValueError):
            verified_reply(self.gateway.handle(sign_request(bad, 'old-v1-secret')), self.public, msg, self.config)
        with self.assertRaises(ValueError):
            verified_reply({'status': 'reserved', 'ticket': '0'*32}, self.public, msg, self.config)
        self.assertFalse(self.send('audit')['reserved'])

    def test_R11_credential_cannot_self_assign_unit(self):
        msg = envelope(self.config, 'reserve', BOOT, task='normal')
        msg.pop('mac');msg['unit'] = 'B'
        with self.assertRaises(ValueError):
            verified_reply(self.gateway.handle(sign_request(msg, self.config['secret'])), self.public, msg, self.config)

    def test_R11_public_key_pin_and_wrong_signer(self):
        wrong_private, wrong_public = create_keys(self.path/'wrong-key')
        with self.assertRaises(ValueError):
            Worker(self.path/'wrong-node', self.config, wrong_public, self.worker_executable, self.gateway.handle)
        msg = envelope(self.config, 'reserve', BOOT, task='normal')
        reply = self.gateway.handle(msg)
        with self.assertRaises(ValueError):
            verified_reply(reply, wrong_public, msg, self.config)

    def test_R12_invalid_first_is_permanent(self):
        q = self.send('reserve', task='invalid')
        self.assertEqual(self.send('submit', task='invalid', ticket=q['ticket'], rows='WRONG\n')['status'], 'invalid')
        expected = rows(self.config['tasks']['invalid']['values'], 4)
        self.assertEqual(self.send('submit', task='invalid', ticket=q['ticket'], rows=expected)['status'], 'rejected')
        self.assertEqual(self.send('reserve', task='invalid')['status'], 'consumed')
        self.assertEqual(self.send('audit', task='invalid')['count'], 0)

    def test_R12_other_units_and_claims_remain_available(self):
        self.node('a').compute('normal')
        self.assertEqual(self.node('b', client_config(self.authority, 'b')).compute('normal')['reply']['status'], 'accepted')
        self.assertEqual(self.node('a').compute('other')['reply']['status'], 'accepted')
        with self.assertRaises(ValueError):
            self.send('reserve', config=client_config(self.authority, 'c'))

    def test_R12_ticket_and_boot_binding(self):
        q = self.send('reserve')
        self.assertEqual(self.send('submit', ticket='0'*32, rows='WRONG')['status'], 'rejected')
        msg = envelope(self.config, 'submit', '11111111-1111-1111-1111-111111111111', task='normal',
                       ticket=q['ticket'], rows=rows(self.config['tasks']['normal']['values'], 4))
        self.assertEqual(verified_reply(self.gateway.handle(msg), self.public, msg, self.config)['status'], 'rejected')


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({'id': test.id(), 'passed': True})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({'id': test.id(), 'passed': False, 'error': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({'id': test.id(), 'passed': False, 'error': self._exc_info_to_string(err, test)})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--report-dir', type=Path, default=ROOT.parents[1]/'artifacts/authority')
    args = p.parse_args()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AdmissionTests))
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir/'local-tests.json').write_text(json.dumps({'passed': result.wasSuccessful(),
          'cases': result.testsRun, 'tests': result.cases}, indent=2)+'\n')
    sys.exit(not result.wasSuccessful())
