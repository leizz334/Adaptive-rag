"""Own a fresh dependency project and finite Mock HTTP worker; preserve existing stacks."""
import asyncio
from datetime import datetime,UTC,timedelta
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import httpx

from app.core.auth import mint_credential
from research.docs.agent_engineering_upgrade.p4_dependency_integration import sandbox

ROOT=Path.cwd()
HERE=ROOT/'research/docs/agent_engineering_upgrade/agent_usability'
OUT=HERE/'evidence'
PRIVATE=Path('/home/panda/.adaptive-rag-usability-20261114')
PROJECT='p4b_usability_20261114_01'
MANIFEST=PRIVATE/'.private'/PROJECT/'manifest.json'
os.umask(0o077)
sandbox.HERE=PRIVATE # Ownership checks point to this new native private test phase only.
os.environ.update(P4B_RUN_LIVE='1',P4B_MANIFEST=str(MANIFEST),DEEPSEEK_API_KEY='',EMBEDDING_API_KEY='',EXPERIENCE_MEMORY_MODE='off')


def save(name,value):
    with (OUT/name).open('x') as stream:json.dump(value,stream,indent=2)


if sys.argv[1]=='setup':
    assert not subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+PROJECT],text=True).strip()
    assert sandbox.prepare(PRIVATE/'.private',PROJECT)==MANIFEST
    sandbox.command(MANIFEST,'up')
    cfg=sandbox.load(MANIFEST)
    from alembic import command
    from alembic.config import Config
    config=Config(str(ROOT/'alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'alembic'))
    config.set_main_option('sqlalchemy.url',cfg['database_url'])
    command.upgrade(config,'head') # Only this fresh owned database; no downgrade/reset.
    async def seed():
        from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
        from app.demo.fixtures import seed_session
        engine=create_async_engine(cfg['database_url'])
        try:
            async with async_sessionmaker(engine)() as db:
                async with db.begin():await seed_session(db)
        finally:await engine.dispose()
    asyncio.run(seed())
    issued={k:mint_credential('web_demo_'+k,datetime.now(UTC)+timedelta(days=2),['user']) for k in ['a','b']}
    credentials={'tokens':{k:v['bearer_token'] for k,v in issued.items()},'credentials':json.dumps({'version':1,'credentials':[v['registry_entry'] for v in issued.values()]})}
    with (PRIVATE/'mock-credentials.json').open('x') as stream:json.dump(credentials,stream)
    save('P2-mock-infrastructure.json',{'project':PROJECT,'new_dependency_containers':3,'original_real_service_untouched':True,'source':'existing P4 sandbox Compose, fresh database head only','paid_requests':0})
    print(json.dumps({'setup':'PASS','project':PROJECT,'paid_requests':0}))
elif sys.argv[1]=='start':
    with httpx.Client(trust_env=False,timeout=1) as client:
        try:
            client.get('http://127.0.0.1:8001/api/v1/health')
            raise RuntimeError('Port8001 occupied; do not replace another service')
        except httpx.TransportError:pass
    sandbox.command(MANIFEST,'ps')
    log=(PRIVATE/'mock-worker.log').open('x')
    worker=subprocess.Popen([sys.executable,'-m','research.docs.agent_engineering_upgrade.agent_usability.mock_worker'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env=os.environ.copy())
    (PRIVATE/'worker.json').write_text(json.dumps({'pid':worker.pid,'module':'research.docs.agent_engineering_upgrade.agent_usability.mock_worker'}))
    with httpx.Client(trust_env=False,timeout=2) as client:
        for _ in range(60):
            if worker.poll() is not None:raise RuntimeError('Mock worker exited; private diagnostic log retained')
            try:
                result=client.get('http://127.0.0.1:8001/api/v1/runtime-status').json()
                if result['available'] and result['verification_only']:break
            except Exception:pass
            time.sleep(1)
        else:raise RuntimeError('Mock runtime readiness timeout')
    credentials=json.loads((PRIVATE/'mock-credentials.json').read_text())
    formal=json.loads(subprocess.check_output(['docker','exec','adaptive-rag-showcase-api-1','python','-c','import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))'],text=True))
    for name,value in [('browser-config.json',{'port':8000,'tokens':formal}),('mode-config.json',{'offline':{'token':formal['a']},'deepseek':{'token':credentials['tokens']['a'],'verification_only':True}})]:
        path=PRIVATE/name
        with path.open('x') as stream:json.dump(value,stream)
        os.chmod(path,0o600);os.chown(path,1000,1000)
    save('P2-mock-started.json',{'pid':worker.pid,'port':8001,'status':result,'key_kind':'synthetic, never reads .env','network':'process socket allowlist loopback only','transport':'HTTPX MockTransport','model_provider':'existing DeepSeekProvider','paid_requests':0})
    print(json.dumps({'mock_started':True,'metadata':result,'paid_requests':0}))
elif sys.argv[1]=='stop':
    row=json.loads((PRIVATE/'worker.json').read_text());pid=row['pid']
    proc=Path('/proc')/str(pid)
    if proc.exists():
        assert row['module'].encode() in (proc/'cmdline').read_bytes()
        os.kill(pid,signal.SIGTERM)
        for _ in range(30):
            if not proc.exists():break
            time.sleep(.2)
    sandbox.command(MANIFEST,'stop')
    save('P4-mock-stopped.json',{'project':PROJECT,'worker_pid':pid,'dependencies_stopped':True,'volumes_retained':True,'budget_retained':str(PRIVATE/'mock-budget/budget.sqlite3'),'paid_requests':0})
    print(json.dumps({'mock_stopped':True,'paid_requests':0}))
