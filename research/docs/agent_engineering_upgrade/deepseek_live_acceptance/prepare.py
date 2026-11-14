"""Prepare isolated runtime inputs; never performs a model HTTP request."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT=Path.cwd()
HERE=ROOT/'research/docs/agent_engineering_upgrade/deepseek_live_acceptance'
OUT=HERE/'evidence'
PRIVATE=Path('/home/panda/.adaptive-rag-live-20261114')
os.umask(0o077)


def docker(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('Docker operation failed; no raw output emitted')
    return result.stdout


cfg=dotenv_values(ROOT/'.env',encoding='utf-8-sig')
key=(cfg.get('DEEPSEEK_API_KEY') or '').strip()
assert key and len(key)<=512 and not any(c.isspace() for c in key)
model=cfg.get('DEEPSEEK_MODEL') or 'deepseek-flash'
assert model=='deepseek-flash','Only currently priced configured model is approved'
base=cfg.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'
url=urlsplit(base)
assert url.scheme=='https' and url.hostname=='api.deepseek.com' and url.path.rstrip('/') in {'','/v1'} and not (url.username or url.password or url.query or url.fragment)
PRIVATE.mkdir(mode=0o700,exist_ok=True)
os.chown(PRIVATE,1000,1000)
secret=PRIVATE/'deepseek.key'
if secret.exists():
    assert not secret.is_symlink() and secret.read_text()==key, 'Existing private key differs; do not replace'
else:
    fd=os.open(secret,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write(key)
os.chmod(secret,0o600)
os.chown(secret,1000,1000)
environment={'REAL_AGENT_KEY_FILE':str(secret),'REAL_AGENT_MODEL':model,'REAL_AGENT_BASE_URL':base,'REAL_AGENT_PORT':'8001','REAL_AGENT_MAX_REQUESTS':'6','REAL_AGENT_MAX_TOKENS':'10000','REAL_AGENT_MAX_USD':'0.05','REAL_AGENT_INPUT_USD_PER_MILLION':'0.30','REAL_AGENT_OUTPUT_USD_PER_MILLION':'1.20'}
config=PRIVATE/'compose.env'
with config.open('x') as stream:
    stream.write(''.join(k+'='+v+'\n' for k,v in environment.items()))
os.chown(config,1000,1000)
probe_code='''
import socket,ssl,json,time
t=time.monotonic()
try:
 count=len(socket.getaddrinfo('api.deepseek.com',443,type=socket.SOCK_STREAM))
 with socket.create_connection(('api.deepseek.com',443),timeout=8) as sock:
  with ssl.create_default_context().wrap_socket(sock,server_hostname='api.deepseek.com') as tls:
   print(json.dumps({'dns_addresses':count,'tls_verified':True,'tls':tls.version(),'elapsed_ms':round((time.monotonic()-t)*1000)}))
except Exception as exc:
 print(json.dumps({'tls_verified':False,'error_type':type(exc).__name__}))
'''
probe=json.loads(docker('run','--rm','--read-only','--cap-drop','ALL','--network','bridge','--entrypoint','python','adaptive-rag-production:be2931f-20261113','-c',probe_code))
assert probe['tls_verified'], 'Container direct TLS failed; do not make paid requests'
baseline=json.loads((OUT/'D1-baseline.json').read_text())
formal=[row for row in baseline['containers'] if row['project']=='adaptive-rag-showcase' and row['name'] in ['/adaptive-rag-showcase-'+s+'-1' for s in ['postgres','redis','qdrant','api']]]
assert len(formal)==4
docker('start',*[row['id'] for name in ['postgres','redis','qdrant','api'] for row in formal if row['name'].endswith('-'+name+'-1')])
for _ in range(45):
    actual=json.loads(docker('inspect',*[r['id'] for r in formal]))
    if all(r['State'].get('Health',{}).get('Status')=='healthy' for r in actual):
        break
    time.sleep(2)
else:
    raise RuntimeError('Original Offline stack failed to become healthy')
for old in formal:
    new=next(r for r in actual if r['Id']==old['id'])
    assert new['Image']==old['image'] and [m.get('Name') for m in new['Mounts']]==old['mounts']
result={'key_native_file_mode':oct(secret.stat().st_mode&0o777),'key_value_disclosed':False,'env_unchanged':hashlib.sha256((ROOT/'.env').read_bytes()).hexdigest()==baseline['env_sha256'],'model':model,'container_network_no_key':probe,'limits':{'requests':6,'reserved_tokens':10000,'usd':'0.05'},'price_upper_bounds_usd_per_million':{'input':'0.30','output':'1.20'},'price_source':'https://api-docs.deepseek.com/quick_start/pricing/','offline_original_four_restored_without_recreation':True,'offline_baseline_active':[{**old,'started':next(r['State']['StartedAt'] for r in actual if r['Id']==old['id'])} for old in formal],'model_http_requests':0}
with (OUT/'D1-prepared.json').open('x') as stream:
    json.dump(result,stream,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='offline_baseline_active'}))
