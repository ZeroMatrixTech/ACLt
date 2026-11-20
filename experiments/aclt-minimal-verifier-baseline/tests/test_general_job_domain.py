# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from general_job import Job, INT, c, digest
from general_vm import fixture,DEFAULT_BUDGET

def job_for(tasks):
    original=fixture(bytes(32),DEFAULT_BUDGET)
    declaration=c.decode(original.declaration);declaration['tasks']=tasks;d=c.encode(declaration)
    plan=c.decode(original.plan);plan.update(tree=list(range(len(tasks))) if len(tasks)>1 else 0,
        dependencies={i:t['double'] for i,t in enumerate(tasks) if 'double' in t},caps=[9000]*len(tasks));p=c.encode(plan)
    execution=c.decode(original.execution);execution.update(declaration_id=digest('Declaration',d),plan_id=digest('Plan',p),budget=sum(plan['caps']))
    return Job(d,p,c.encode(execution),original.artifacts)

class IntegerVectorDomainTests(unittest.TestCase):
    def test_seventeen_tasks_and_full_i64_literal_range(self):
        self.assertEqual(len(job_for([{'literal':n} for n in range(17)]).tasks),17)
        for value in (-2**63,2**63-1):
            self.assertEqual(job_for([{'literal':value},{'literal':1},{'double':1}]).tasks[0]['literal'],value)
    def test_outside_i64_and_actual_overflow_rejected(self):
        for value in (-2**63-1,2**63):
            with self.assertRaises(c.CodecError):job_for([{'literal':value}])
        for value in (-2**63,2**63-1):
            job=job_for([{'literal':value},{'double':0}])
            with self.assertRaisesRegex(c.CodecError,'task result is outside i64'):
                job.check_output(1,{'outcome':'OK','output':INT.pack(0)},{0:{'output':INT.pack(value)}})
    def test_actual_in_range_double_compares_output_bytes(self):
        value=2**62-1;job=job_for([{'literal':value},{'double':0}]);accepted={0:{'output':INT.pack(value)}}
        job.check_output(1,{'outcome':'OK','output':INT.pack(2*value)},accepted)
        with self.assertRaisesRegex(c.CodecError,'output violates task family'):
            job.check_output(1,{'outcome':'OK','output':INT.pack(0)},accepted)
