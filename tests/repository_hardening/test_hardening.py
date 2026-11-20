# SPDX-License-Identifier: Apache-2.0
import ast
import copy
from email.message import Message
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from tools import test_control as http
from tools.repository_checks import source_baseline,check_documents
from repository_files import delivery_files,tracked_coverage

class Frames(unittest.TestCase):
    def handler(self,headers,body=b'{}'):
        class Connection:
            def settimeout(self,n):self.timeout=n
        class Server:control_token=b'a'*64
        class Fake:pass
        obj=Fake();obj.headers=Message();obj.rfile=io.BytesIO(body);obj.connection=Connection();obj.server=Server()
        for k,v in headers:obj.headers[k]=v
        return obj
    def test_authentication_precedes_body_reads(self):
        for auth in ([],[('Authorization','Bearer '+ 'b'*64)]):
            obj=self.handler(auth+[('Content-Length','2')])
            with self.assertRaises(PermissionError):http.request(obj)
            self.assertEqual(obj.rfile.tell(),0)
    def test_lengths_transfer_and_truncation_are_rejected(self):
        auth=[('Authorization','Bearer '+'a'*64)]
        for headers,body in [([],b''),([('Content-Length','-1')],b''),([('Content-Length','65537')],b''),([('Content-Length','3')],b'{}'),([('Content-Length','2'),('Content-Length','2')],b'{}'),([('Content-Length','2'),('Transfer-Encoding','chunked')],b'{}')]:
            with self.subTest(headers=headers):
                with self.assertRaises(ValueError):http.request(self.handler(auth+headers,body))
    def test_json_duplicates_constants_and_depth_are_rejected(self):
        for body in (b'{"a":1,"a":2}',b'{"a":NaN}',b'['*25+b'0'+b']'*25,b'[]'):
            obj=self.handler([('Authorization','Bearer '+'a'*64),('Content-Length',str(len(body)))],body)
            with self.assertRaises(ValueError):http.request(obj)
    def test_valid_frame_and_timeout(self):
        obj=self.handler([('Authorization','Bearer '+'a'*64),('Content-Length','2')]);self.assertEqual(http.request(obj),{});self.assertEqual(obj.connection.timeout,http.TIMEOUT)
    def test_authenticated_frame_above_former_engineering_limits(self):
        value={'items':[0]*12000,'padding':'x'*70000,'nested':{'v':[[0]]}}
        for _ in range(32):value['nested']={'next':value['nested']}
        body=json.dumps(value).encode()
        obj=self.handler([('Authorization','Bearer '+'a'*64),('Content-Length',str(len(body)))],body)
        self.assertEqual(http.request(obj),value)

    def test_private_token_file_and_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'token';p.write_bytes(b'a'*64);p.chmod(0o600);self.assertEqual(http.token_file(p),b'a'*64)
            p.chmod(0o644)
            with self.assertRaises(ValueError):http.token_file(p)
            link=Path(td)/'link';link.symlink_to(p)
            with self.assertRaises(OSError):http.token_file(link)
            for token in (b'',b'a'*31,b'a'*257,b'a '*32):
                with self.assertRaises(ValueError):http.validate_token(token)

class Repository(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_authority_private_key_is_exclusive_before_generation(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('hardened_authority_protocol',ROOT/'experiments/aclt-authority-admission/protocol.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        private,public=module.create_keys(self.root/'keys')
        import stat
        self.assertEqual(stat.S_IMODE(private.stat().st_mode),0o600)
        before=private.read_bytes()
        with self.assertRaises(FileExistsError):module.create_keys(self.root/'keys')
        self.assertEqual(private.read_bytes(),before)
        linkdir=self.root/'linked';linkdir.mkdir();target=self.root/'absent';(linkdir/'authority.key').symlink_to(target)
        with self.assertRaises(FileExistsError):module.create_keys(linkdir)
        self.assertFalse(target.exists())
    def test_baseline_sha_gate_is_disabled(self):
        d=self.root/'docs/testing';d.mkdir(parents=True)
        for name in ('SOURCE-BASELINE.json','SOURCE-BASELINE-correction-20261105.json'):shutil.copyfile(ROOT/'docs/testing'/name,d/name)
        self.assertEqual(source_baseline(self.root)['pins'],43)
        p=d/'SOURCE-BASELINE.json';v=json.loads(p.read_text());v['final_repository_head']=v['main'];p.write_text(json.dumps(v))
        self.assertEqual(source_baseline(self.root)['status'],'DISABLED')
    def test_sha_gate_does_not_read_source_blobs(self):
        def unused(*args):raise AssertionError('SHA source verifier was called')
        self.assertEqual(source_baseline(ROOT,unused)['source_verification'],'DISABLED')
    def test_live_document_checks_and_qualifier_boundary(self):
        d=self.root/'docs/06-research';d.mkdir(parents=True);(self.root/'docs/05-decisions').mkdir()
        p=d/'claims-and-sources.md';p.write_text('| CLM-X | text | OPEN | `UNREGISTERED` | type | — | — | ref | scope |\n')
        with self.assertRaises(ValueError):check_documents(self.root)
        p.write_text('| CLM-X | text | OPEN | `HYPOTHESIS` | type | — | — | ref | scope |\n');self.assertEqual(check_documents(self.root)['claims'],1)
    def test_duplicate_decisions_and_broken_links_fail(self):
        d=self.root/'docs/06-research';d.mkdir(parents=True);(d/'claims-and-sources.md').write_text('| CLM-X | t | OPEN | `HYPOTHESIS` | type | — | — | ref | scope |\n')
        adr=self.root/'docs/05-decisions';adr.mkdir();(adr/'ADR-0001-a.md').write_text('# x');(adr/'ADR-0001-b.md').write_text('# x')
        with self.assertRaises(ValueError):check_documents(self.root)
        (adr/'ADR-0001-b.md').unlink();(adr/'ADR-0001-a.md').write_text('[broken](not-found.md)')
        with self.assertRaises(ValueError):check_documents(self.root)
    def test_inventory_includes_histories_and_arbitrary_build_source(self):
        names={p.relative_to(ROOT).as_posix() for p in delivery_files(ROOT)}
        self.assertNotIn('AGENTS.md',names);self.assertFalse(any(p.startswith('.claude/') for p in names));self.assertTrue(any(p.startswith('docs/codocs/') for p in names));self.assertTrue(any(p.startswith('experiments/aclt-minimal-verifier-state2/') for p in names))
        cfg=json.loads((ROOT/'DELIVERY-SCOPE.json').read_text());(self.root/'DELIVERY-SCOPE.json').write_text(json.dumps(cfg))
        for n in cfg['top_level_files']:
            p=self.root/n;p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():p.write_text('test')
        p=self.root/'tools/extra/build/x.py';p.parent.mkdir(parents=True);p.write_text('x=1')
        self.assertIn(p,delivery_files(self.root))
    def test_symlinked_source_root_is_never_traversed(self):
        cfg=json.loads((ROOT/'DELIVERY-SCOPE.json').read_text());(self.root/'DELIVERY-SCOPE.json').write_text(json.dumps(cfg))
        external=self.root/'external';external.mkdir();(external/'secret.py').write_text('not a source input')
        (self.root/'tools').symlink_to(external,target_is_directory=True)
        with self.assertRaises(ValueError):delivery_files(self.root)
    def test_delivery_policy_version_must_be_current(self):
        cfg=json.loads((ROOT/'DELIVERY-SCOPE.json').read_text())
        (self.root/'DELIVERY-SCOPE.json').write_text(json.dumps(dict(cfg,schema='aclt.delivery-scope@1')))
        with self.assertRaisesRegex(ValueError,'delivery policy version'):delivery_files(self.root)
    def test_delivery_policy_rule_order_is_enforced(self):
        cfg=json.loads((ROOT/'DELIVERY-SCOPE.json').read_text())
        (self.root/'DELIVERY-SCOPE.json').write_text(json.dumps(dict(cfg,classification_order=['digest_patterns','never_digest_patterns'])))
        with self.assertRaisesRegex(ValueError,'classification order'):delivery_files(self.root)
    def test_unknown_tracked_paths_cannot_hide_outside_inventory(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'new-root.txt').write_text('test');subprocess.run(['git','-C',str(self.root),'add','new-root.txt'],check=True)
        shutil.copyfile(ROOT/'DELIVERY-SCOPE.json',self.root/'DELIVERY-SCOPE.json')
        with self.assertRaises(ValueError):tracked_coverage(self.root,[])
    def test_optimized_validator_fails_before_creating_output(self):
        names=[]
        for base in ('scripts','tools','experiments'):
            for path in (ROOT/base).rglob('*.py'):
                name=path.relative_to(ROOT).as_posix()
                if any(x in path.parts for x in ('build','target','artifacts','__pycache__','.toolchain')):continue
                if name.startswith(('experiments/aclt-minimal-verifier/','experiments/aclt-minimal-verifier-state2/')) or '/tests/' in name:continue
                if any(isinstance(node,ast.Assert) for node in ast.walk(ast.parse(path.read_text()))):names.append(name)
        self.assertTrue(names)
        for name in names:
            r=subprocess.run([sys.executable,'-O','-B',str(ROOT/name),'--help'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0,name);self.assertIn('without -O',r.stderr)
if __name__=='__main__':unittest.main()
