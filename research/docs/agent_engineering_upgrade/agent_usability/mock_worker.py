"""Explicit simulated DeepSeek transport, real business backends; loopback sockets only."""
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys

import httpx
from pydantic import SecretStr

from app.agents.answer_evidence import safe_answer
from app.config.settings import Settings
from app.demo.real_dev import RuntimeConfig,create_application
from app.providers.paid_budget import BudgetLimits
from app.prompts.answer import ANSWER_SYSTEM
from app.schemas.agent import ToolResult
from eval.memory_ablation import ScriptedProvider

PRIVATE=Path('/home/panda/.adaptive-rag-usability-20261114')
PROJECT='p4b_usability_20261114_01'
cfg=json.loads((PRIVATE/'.private'/PROJECT/'manifest.json').read_text())
credentials=json.loads((PRIVATE/'mock-credentials.json').read_text())
os.environ['REAL_AGENT_PAID_AUTHORIZED']='true' # Only this fake-key, network-blocked Mock process.
os.environ['EXPERIENCE_MEMORY_MODE']='off'
logging.disable(logging.CRITICAL)

# Process-scoped hard block independent of HTTPX: no external socket can send.
import socket
original=socket.socket.connect
original_ex=socket.socket.connect_ex
def check(address):
    if isinstance(address,tuple) and address[0] not in {'127.0.0.1','::1','localhost'}:
        raise OSError('Mock acceptance forbids external network')
def connect(sock,address):check(address);return original(sock,address)
def connect_ex(sock,address):check(address);return original_ex(sock,address)
socket.socket.connect=connect
socket.socket.connect_ex=connect_ex

settings=Settings(_env_file=None,app_env='production',database_url=cfg['database_url'],redis_url=cfg['redis_url'],qdrant_url=cfg['qdrant_url'],qdrant_collection=cfg['collection'],deepseek_api_key=SecretStr('synthetic-mock-provider-no-network'),deepseek_model='deepseek-flash',deepseek_thinking_mode='disabled',llm_max_retries=1,auth_mode='required',auth_credentials=credentials['credentials'],knowledge_mode='private',memory_mode='M2',local_embedding_enabled=False,cross_encoder_enabled=False,unstructured_enabled=False,mcp_enabled=False,log_level='WARNING',rate_limit_per_minute=10000,agent_tracing_enabled=True,agent_tracing_backend='local')
budget=PRIVATE/'mock-budget'
budget.mkdir(exist_ok=True,mode=0o700)
config=RuntimeConfig(settings,BudgetLimits(200,1_000_000,Decimal('2'),Decimal('0.30'),Decimal('1.20'),'deepseek-flash'),budget/'budget.sqlite3')
scripted=ScriptedProvider()
counter=0


async def respond(request):
    global counter
    body=json.loads(request.content)
    assert body['model']=='deepseek-flash' and request.url.host=='api.deepseek.com'
    messages=body['messages']
    output=await scripted.generate(messages,temperature=body['temperature'],max_tokens=body['max_tokens'],response_format=body.get('response_format'))
    if messages[0]['content']==ANSWER_SYSTEM:
        user=messages[-1]['content']
        raw=user.split('工具结果：\n',1)[1].split('\n\n输出 JSON',1)[0]
        try:tools=[ToolResult.model_validate(row) for row in json.loads(raw)]
        except (ValueError,TypeError):tools=[]
        evidence=user.split('检索证据：\n',1)[-1].split('\n\n工具结果：',1)[0]
        chunk_ids=re.findall(r'\[([^\]\n]+)\]',evidence) if evidence!='(无检索结果)' else []
        if tools:
            value={'answer':safe_answer(tools),'citation_chunk_ids':[],'refused':False}
        elif chunk_ids:
            text=evidence.split('\n',1)[-1][:500]
            value={'answer':text,'citation_chunk_ids':chunk_ids,'refused':False}
        else:
            value={'answer':'模拟验证服务：现有资料不足，请补充信息。','citation_chunk_ids':[],'refused':False}
        content=json.dumps(value,ensure_ascii=False)
    else:
        content=output.content
    counter+=1
    incoming=max(1,len(request.content)//4)
    outgoing=max(1,min(body['max_tokens'],len(content.encode())//4))
    return httpx.Response(200,json={'id':'mock-'+str(counter),'model':body['model'],'choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':incoming,'completion_tokens':outgoing,'total_tokens':incoming+outgoing}})


app=create_application(config,transport=httpx.MockTransport(respond))
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8001,access_log=False,log_level='warning')
