#!/usr/bin/env python3
import pathlib, random, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKER = ROOT / 'build/worker'
VERIFIER = ROOT / 'target/debug/aclt-minimal-verifier'
tests = 0

def run(argv):
    return subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=10)

with tempfile.TemporaryDirectory() as temp:
    source, result = pathlib.Path(temp)/'input.txt', pathlib.Path(temp)/'results.txt'
    def verify(data, chunk, rows, accepted):
        global tests
        source.write_text(data)
        result.write_text(rows)
        proc = run([VERIFIER, source, chunk, result])
        assert (proc.returncode == 0) == accepted, (data[:80], rows[:100], proc.stderr)
        tests += 1
        return proc

    rng = random.Random(20261002)
    cases = [[3,-1,8,0,-7,12,5,2,-3,9], [0], [-1000000000,1000000000],
             [1000000000]*100000, [-1000000000]*100000]
    cases += [[rng.randint(-1000000000,1000000000) for _ in range(rng.randint(1,300))] for _ in range(30)]
    for values in cases:
        data = ' '.join(map(str,values)) + '\n'
        chunk = rng.randint(1,100) if len(values)<100000 else 4096
        source.write_text(data)
        worker = run([WORKER,source,chunk])
        assert worker.returncode == 0, worker.stderr
        proc = verify(data,chunk,worker.stdout,True)
        assert f'sum={sum(values)} min={min(values)} max={max(values)}' in proc.stdout

    data='3 -1 8 0 -7 12 5 2 -3 9\n'
    source.write_text(data)
    rows=run([WORKER,source,4]).stdout.splitlines()
    mutations=[rows[:-1],rows+[rows[0]],[rows[0],rows[0],rows[2]],list(reversed(rows)),
               [rows[0]+' 99']+rows[1:],['bad']+rows[1:],['']+rows]
    for column in range(6):
        fields=rows[0].split(); fields[column]=str(int(fields[column])+1)
        mutations.append([' '.join(fields)]+rows[1:])
    for mutation in mutations:
        verify(data,4,'\n'.join(mutation)+'\n',False)
    verify(data.replace('12','13'),4,'\n'.join(rows)+'\n',False)
    for invalid in ['', 'x', '01', '+1', '-0', '1.5', '1000000001', '-1000000001',
                    '9223372036854775808', '1 '*100001, '1 '*1000001]:
        source.write_text(invalid)
        assert run([WORKER,source,4]).returncode != 0
        verify(invalid,4,'',False)
    for chunk in ['0','-1','100001','+4','x']:
        source.write_text(data)
        assert run([WORKER,source,chunk]).returncode != 0
        verify(data,chunk,'',False)
    verify(data,4,'x'*12000001,False)
    # All six ASCII whitespace characters must agree across C++ and Rust.
    data = '1\t2\n3\r4\v5\f6 '
    source.write_text(data)
    worker = run([WORKER,source,2])
    assert worker.returncode == 0
    verify(data,2,worker.stdout,True)
    # Smallest chunks at maximum input size produce over 2 MB of valid output.
    data = '1000000000 '*100000
    source.write_text(data)
    worker = run([WORKER,source,1])
    assert worker.returncode == 0 and len(worker.stdout) > 2000000
    verify(data,1,worker.stdout,True)
print(f'PASS: {tests} verification cases; worker input rejection and Python reference totals checked')
