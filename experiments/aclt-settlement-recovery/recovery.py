# SPDX-License-Identifier: Apache-2.0
"""Same v2 transitions; explicit test callbacks bracket the actual SQL COMMIT."""
from contextlib import closing
from context import *
from ledger import Ledger


class RecoveryLedger(Ledger):
    def __init__(self,*args,test_hook=None,**kwargs):
        self.test_hook=test_hook
        super().__init__(*args,**kwargs)

    def handle(self,packet):
        req=self.authenticate(packet)
        with closing(self.connect()) as c:
            try:
                c.execute('BEGIN IMMEDIATE')
                status,result=self.transition(c,req)
                event=self.append(c,req['op'],{'request':packet,'status':status,'result':result})
                info={'op':req['op'],'policy_id':req['data'].get('policy_id',ZERO).hex(),
                      'status':status,'request_digest':sha(packet).hex(),'event_ref':event.hex(),
                      'receipt_digest':sha(result['receipt']).hex() if 'receipt' in result else ''}
                if self.test_hook: self.test_hook('before_commit',info)
                c.execute('COMMIT')
                if self.test_hook: self.test_hook('after_commit',info)
            except BaseException:
                if c.in_transaction: c.execute('ROLLBACK')
                raise
        return sign({'schema_id':'aclt.exp.funding-response@2','authority_id':self.authority,
                     'request_digest':sha(packet),'nonce':req['nonce'],'op':req['op'],
                     'status':status,'event_ref':event,'result':result},self.private)
