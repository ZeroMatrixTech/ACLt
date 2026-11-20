
if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import concurrent.futures,hashlib,importlib,json,os,pathlib,sqlite3,sys,tempfile
B=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(B))
from ledger import Store
from receiver import Receiver
from protocol import envelope,rows,digest,claim,check
tests=[]
def ok(name,condition):assert condition,name;tests.append({'name':name,'passed':True})
def rejected(name,fn):
 try:fn()
 except Exception:ok(name,True)
 else:raise AssertionError(name)
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'db%? name';s=Store.create(str(p),'config');boot='00000000-0000-0000-0000-000000000000'
 rejected('no-reinitialize',lambda:Store.create(str(p),'config'))
 ok('config-sha-consistency-DISABLED',Store(str(p),'wrong') is not None)
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:rs=list(pool.map(lambda _:s.reserve('claim','unit',boot),range(16)))
 ok('concurrent-one-reservation',sum(r['status']=='reserved' for r in rs)==1)
 ticket=next(r['ticket'] for r in rs if r['status']=='reserved')
 ok('bad-ticket',s.submit('claim','unit',boot,'bad','digest')['status']=='rejected')
 ok('bad-boot',s.submit('claim','unit','other',ticket,'digest')['status']=='rejected')
 a=s.submit('claim','unit',boot,ticket,'digest');ok('accept',a['status']=='accepted')
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:ds=list(pool.map(lambda _:s.submit('claim','unit',boot,ticket,'digest'),range(16)))
 ok('concurrent-duplicates-stable',all(d=={'status':'duplicate','receipt':a['receipt']} for d in ds))
 c=s.submit('claim','unit',boot,ticket,'changed',valid=False)
 ok('conflict-no-replacement',c=={'status':'conflict','receipt':a['receipt']})
 before=p.read_bytes();au=s.audit('claim');ok('one-contribution',au['count']==1 and au['slots'][0]['conflict']==1)
 ok('audit-readonly-no-ticket',p.read_bytes()==before and 'ticket' not in au['slots'][0])
 fresh=Store(str(p),'config');ok('restart-stable',fresh.audit('claim')==au and fresh.reserve('claim','unit',boot)=={'status':'consumed'})
 q=fresh.reserve('bad','unit',boot);ok('invalid-first-zero',fresh.submit('bad','unit',boot,q['ticket'],'wrong',valid=False)['status']=='invalid')
 ok('invalid-never-refunded',fresh.submit('bad','unit',boot,q['ticket'],'correct')['status']=='rejected' and fresh.audit('bad')['count']==0)
 p.unlink();rejected('missing-after-open-no-recreate',lambda:s.reserve('new','unit',boot));ok('missing-stays-missing',not p.exists())
 rejected('constructor-no-recreate',lambda:Store(str(p),'config'));ok('constructor-missing-stays-missing',not p.exists())
 link=pathlib.Path(td)/'link';link.symlink_to(p);rejected('symlink-rejected',lambda:Store(str(link),'config'))
 corrupt=pathlib.Path(td)/'corrupt';corrupt.write_bytes(b'broken');rejected('corruption-failclosed',lambda:Store(str(corrupt),'config'))
 manifest={'keys':{'a':{'unit':'A','secret':'test-a'},'alias':{'unit':'A','secret':'test-alias'},'b':{'unit':'B','secret':'test-b'},'c':{'unit':'C','secret':'test-c'}},'tasks':{'t':{'values':[3,-1,8,0],'chunk':2,'units':['A','B']},'alias-task':{'values':[3,-1,8,0],'chunk':2,'units':['A','B']}}}
 r=Receiver(manifest,str(pathlib.Path(td)/'receiver'),True)
 def send(op,key='a',task='t',**extra):
  secret=manifest['keys'][key]['secret'];m=envelope(op,key,task,boot,secret,**extra);return check(r.handle(m),secret)['reply']
 q=send('reserve');ok('protocol-reserve',q['status']=='reserved')
 ok('alias-key-consumed',send('reserve','alias')['status']=='consumed')
 ok('alias-task-consumed',send('reserve',task='alias-task')['status']=='consumed')
 rejected('unit-not-eligible',lambda:send('reserve','c'))
 rejected('unknown-key',lambda:r.handle(envelope('reserve','unknown','t',boot,'unknown')))
 m=envelope('reserve','b','t',boot,'wrong');rejected('bad-mac',lambda:r.handle(m))
 m=envelope('reserve','b','t',boot,'test-b',unit='NEW');rejected('self-reported-unit-rejected',lambda:r.handle(m))
 good=rows(manifest['tasks']['t']['values'],2);a=send('submit',ticket=q['ticket'],rows=good)
 ok('protocol-valid-accept',a['status']=='accepted')
 ok('protocol-duplicate',send('submit',ticket=q['ticket'],rows=good)['receipt']==a['receipt'])
 ok('math-invalid-conflict-no-vote',send('submit',ticket=q['ticket'],rows=good.replace(' 2 ', ' 3 ',1))['status']=='conflict' and send('audit')['count']==1)
 qb=send('reserve','b');ok('different-enrolled-unit-reserved',qb['status']=='reserved')
 ok('different-unit-independent-slot',send('submit','b',ticket=qb['ticket'],rows=good)['status']=='accepted' and send('audit')['count']==2)
 altered=json.loads(json.dumps(manifest));altered['tasks']['alias-task']['chunk']=1
 rejected('ambiguous-alias-contract',lambda:Receiver(altered,str(pathlib.Path(td)/'ambiguous'),True))
(pathlib.Path(os.environ.get('ACLT_REPORT_DIR',str(B)))/'local-tests.json').write_text(json.dumps({'sha_consistency':'DISABLED','passed':True,'cases':len(tests),'tests':tests},indent=2)+'\n');print('PASS',len(tests),'local checks')

from ordering_checks import run_checks
with tempfile.TemporaryDirectory() as td:
 orders=run_checks(Store,pathlib.Path(td))
 print("PASS",len(orders),"orders /",len(orders)*4,"transitions")
