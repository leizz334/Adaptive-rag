"""Actual authenticated HTTP/SSE/SQL workflows using only the labelled Mock transport."""
import json
import logging
import os
from pathlib import Path
import subprocess
import time

import httpx

from app.providers.paid_budget import AttemptLedger,BudgetLimits
from decimal import Decimal

ROOT=Path.cwd()
HERE=ROOT/'research/docs/agent_engineering_upgrade/agent_usability'
OUT=HERE/'evidence'
PRIVATE=Path('/home/panda/.adaptive-rag-usability-20261114')
PROJECT='p4b_usability_20261114_01'
cfg=json.loads((PRIVATE/'.private'/PROJECT/'manifest.json').read_text())
tokens=json.loads((PRIVATE/'mock-credentials.json').read_text())['tokens']
os.umask(0o077)
logging.disable(logging.CRITICAL)
client=httpx.Client(base_url='http://127.0.0.1:8001/api/v1',trust_env=False,timeout=30)


def req(method,path,data=None,subject='a',expected=200,stream=False):
    response=client.request(method,path,json=data,headers={'Authorization':'Bearer '+tokens[subject]} if subject else {})
    assert response.status_code==expected,f'{method} {path} returned{response.status_code}, expected{expected}'
    return [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')] if stream else response.json()


def save(name,value):
    with (OUT/name).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def trace(answer):
    data=req('GET',f'/sessions/{answer["session_id"]}/traces/{answer["root_run_id"]}')
    save('mock-trace-'+answer['root_run_id']+'.json',data)
    return data


def sql(query):
    return json.loads(subprocess.check_output(['docker','exec',PROJECT+'-postgres-1','psql','-U','p4b','-d',PROJECT,'-Atc',query],text=True))


status=req('GET','/runtime-status',subject=None)
assert status['mode']=='deepseek' and status['available'] and status['verification_only']
req('GET','/auth/me',subject=None,expected=401)
checks={}
first=req('POST','/chat',{'message':'请查询 ORD95101 的订单状态和金额'})
t1=trace(first)
actual=sql("SELECT row_to_json(t) FROM (SELECT order_id,status,total_cents FROM orders WHERE order_id='ORD95101') t")
assert any(t['name']=='get_order' and t['success'] and t['result']['total_cents']==actual['total_cents']==6800 and t['result']['status']==actual['status'] for t in t1['tools'])
assert '68' in first['answer']
events=req('POST','/chat/stream',{'message':'这单的商品明细和是否定制也帮我核实','session_id':first['session_id']},stream=True)
assert not any(e['event']=='error' for e in events)
second=next(e['data'] for e in events if e['event']=='answer')
t2=trace(second)
assert second['session_id']==first['session_id'] and '演示帆布包' in second['answer']
assert t2['memory']['mode']=='M2' and t2['memory']['message_count']>0
assert any(t['name']=='get_order_items' and t['success'] and t['result']['item_count']==1 for t in t2['tools'])
save('P2-order-memory.json',{'transport':'MockTransport, not live DeepSeek','database':actual,'first':first,'followup':second,'events':[e['event'] for e in events]})
checks['order_tool_calling']='PASS_MOCK_HTTP_SQL'
checks['memory_multiturn']='PASS_MOCK_HTTP_SSE'

doc='usability-policy-20261114'
question='琥珀验收定制商品过了七天，但有质量问题还能退吗？'
policy=question+'定制商品不适用七天无理由退货；质量问题超过七天仍可申请售后退换，须提供合成凭证并经过审核。本段仅用于隔离验证。'
req('POST','/knowledge/documents/'+doc,{'title':'琥珀验收合成售后政策','content':policy})
own=req('POST','/knowledge/search',{'query':question,'mode':'hybrid'})
foreign=req('POST','/knowledge/search',{'query':question,'mode':'hybrid'},subject='b')
assert any(c['document_id']==doc for c in own['chunks']) and not foreign['chunks']
grounded=req('POST','/chat',{'message':question})
gt=trace(grounded)
assert any(c['document_id']==doc for c in grounded['citations'])
assert '质量问题' in grounded['answer'] and any(c['document_id']==doc for c in gt['retrieval'])
req('DELETE','/knowledge/documents/'+doc,subject='b',expected=404)
save('P2-rag.json',{'transport':'MockTransport, not live DeepSeek','response':grounded,'own_hits':len(own['chunks']),'foreign_hits':len(foreign['chunks'])})
checks['rag_citations']='PASS_MOCK_REAL_PRIVATE_RETRIEVAL'

before=sql("SELECT json_build_object('status',(SELECT status FROM orders WHERE order_id='ORD95103'),'audit',(SELECT count(*) FROM audit_logs),'idempotency',(SELECT count(*) FROM idempotency_keys))")
assert before['status']=='paid'
proposal=req('POST','/chat',{'message':'请取消订单 ORD95103'})
pt=trace(proposal)
assert proposal['pending_action']['tool_name']=='cancel_order'
assert sql("SELECT to_json(status) FROM orders WHERE order_id='ORD95103'")=='paid'
action=proposal['pending_action']['action_id']
path=f'/sessions/{proposal["session_id"]}/actions/{action}'
req('POST',path+'/cancel',subject='b',expected=404)
payload={'message':'确认执行','session_id':proposal['session_id'],'confirm_action_id':action,'idempotency_key':action}
confirmed=req('POST','/chat',payload)
after=sql("SELECT json_build_object('status',(SELECT status FROM orders WHERE order_id='ORD95103'),'audit',(SELECT count(*) FROM audit_logs),'idempotency',(SELECT count(*) FROM idempotency_keys))")
replay=req('POST','/chat',payload)
again=sql("SELECT json_build_object('status',(SELECT status FROM orders WHERE order_id='ORD95103'),'audit',(SELECT count(*) FROM audit_logs),'idempotency',(SELECT count(*) FROM idempotency_keys))")
assert after==again and after['status']=='cancelled'
assert after['audit']==before['audit']+1 and after['idempotency']==before['idempotency']+1
assert '已取消' in confirmed['answer'] and '已取消' in replay['answer']
assert req('GET',path)['status']=='completed'
req('POST',path+'/cancel',expected=409)
save('P2-hitl.json',{'transport':'MockTransport, actual DB write after confirmation','before':before,'proposal':proposal,'confirmed':confirmed,'replay':replay,'after':after,'after_replay':again,'nodes':pt['nodes']})
checks['hitl_idempotency']='PASS_MOCK_REAL_DB_CONFIRMATION'

req('POST','/chat',{'message':'查询 ORD95101','user_id':'web_demo_a'},subject='b',expected=403)
req('GET',f'/sessions/{first["session_id"]}/messages',subject='b',expected=404)
not_owned=req('POST','/chat',{'message':'请查询 ORD95101 的状态'},subject='b')
nt=trace(not_owned) if False else req('GET',f'/sessions/{not_owned["session_id"]}/traces/{not_owned["root_run_id"]}',subject='b')
assert all(not t['success'] for t in nt['tools']) and '无法查到' in not_owned['answer']
unknown=req('POST','/chat',{'message':'请查询订单 ORD999999999 的状态'})
ut=trace(unknown)
assert any(not t['success'] and t['name']=='get_order' for t in ut['tools']) and '无法查到' in unknown['answer']
missing=req('POST','/chat',{'message':'月桂不存在保修政策是什么？'},subject='b')
assert not missing['citations'] and missing['refused']
save('P2-negative-owner.json',{'not_owned':not_owned,'unknown_order':unknown,'missing_policy':missing,'forged_subject_status':403,'foreign_history_status':404})
checks['negative_and_owner']='PASS_MOCK_CONTROLLED_DEGRADATION'

book=AttemptLedger(PRIVATE/'mock-budget/budget.sqlite3',BudgetLimits(200,1_000_000,Decimal('2'),Decimal('0.30'),Decimal('1.20'),'deepseek-flash'))
snapshot=book.snapshot()
assert snapshot['settled']>0 and snapshot['tokens']<snapshot['reserved_tokens']
assert not(snapshot['pending'] or snapshot['uncertain'])
save('P2-mock-acceptance.json',{'checks':checks,'mock_ledger':snapshot,'paid_provider_requests':0,'real_business_results':{name:'NOT_RUN_NO_PAID_AUTHORIZATION' for name in ['ToolCalling','Memory','RAG','negative','HITL']},'provider':'existing DeepSeekProvider with HTTPX MockTransport; no real Key','security':'original Bearer/Owner/HITL/idempotency/rate limit paths retained'})
print(json.dumps({'checks':checks,'mock_ledger':snapshot,'paid_provider_requests':0}))
client.close()
