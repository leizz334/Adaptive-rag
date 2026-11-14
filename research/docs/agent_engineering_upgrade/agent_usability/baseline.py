"""Read-only original-resource snapshot; copy the old budget without changing it."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path.cwd()
HERE=ROOT/'research/docs/agent_engineering_upgrade/agent_usability'
OUT=HERE/'evidence'
PRIVATE=Path('/home/panda/.adaptive-rag-usability-20261114')
os.umask(0o077)
OUT.mkdir(exist_ok=True)
PRIVATE.mkdir(exist_ok=True,mode=0o700)
os.chown(PRIVATE,1000,1000)


def docker(*args):
    p=subprocess.run(['docker',*args],capture_output=True,text=True)
    assert p.returncode==0,'Read-only Docker snapshot failed; no private output emitted'
    return p.stdout


ids=docker('ps','-aq').split()
rows=json.loads(docker('inspect',*ids))
containers=[{'id':r['Id'],'name':r['Name'],'image':r['Image'],'state':r['State']['Status'],'started':r['State']['StartedAt'],'project':r['Config']['Labels'].get('com.docker.compose.project'),'service':r['Config']['Labels'].get('com.docker.compose.service'),'ports':r['HostConfig']['PortBindings'],'mounts':[m.get('Name') for m in r['Mounts']]} for r in rows]
api=next(r for r in containers if r['name']=='/adaptive-rag-real-agent-dev-api-1')
assert api['state']=='exited','Original real service must remain stopped this zero-paid phase'
volume='adaptive-rag-real-agent-dev_real_budget'
assert volume in docker('volume','ls','--format','{{.Name}}').splitlines()
code='''
import hashlib,json,sqlite3,shutil,os
from decimal import Decimal
from pathlib import Path
p=Path('/ledger/budget.sqlite3')
with sqlite3.connect('file:/ledger/budget.sqlite3?mode=ro',uri=True) as db:
 rows=db.execute('SELECT id,tokens,usd,state FROM attempts ORDER BY id').fetchall()
 assert db.execute('PRAGMA quick_check').fetchall()==[('ok',)]
result={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'attempts':rows,'requests':len(rows),'tokens':sum(r[1] for r in rows),'usd':str(sum((Decimal(r[2]) for r in rows),Decimal(0))),'mode':oct(p.stat().st_mode&0o777)}
backup=Path('/backup/legacy-before.sqlite3')
assert not backup.exists()
shutil.copyfile(p,backup)
os.chmod(backup,0o600)
print(json.dumps(result))
'''
budget=json.loads(docker('run','--rm','--network','none','--read-only','--cap-drop','ALL','-v',volume+':/ledger:ro','-v',str(PRIVATE)+':/backup:rw','--entrypoint','python',api['image'],'-c',code))
env_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'.env',Path('/mnt/d/Code/Adaptive-rag/.env')] if p.is_file()}
result={'containers':containers,'volumes':docker('volume','ls','--format','{{.Name}}').splitlines(),'original_budget':budget,'private_budget_copy':str(PRIVATE/'legacy-before.sqlite3'),'env_sha256':env_hashes,'paid_authorization':False}
with (OUT/'baseline.json').open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps({'original_budget':budget,'containers':len(containers),'volumes':len(result['volumes']),'env_files_hashed':len(env_hashes),'paid_requests':0}))
