"""Append only a verified commit pack; never touch damaged loose objects."""
import hashlib
import os
from pathlib import Path
import subprocess

CACHE = Path('C:/Users/panda/.codex/recovery/Adaptive-rag-20261113-467df67775c0485fbcd23b50481ed14a.git')
ORIGINAL = Path('D:/Code/Adaptive-rag/.git')
env = os.environ.copy()
env['GIT_OBJECT_DIRECTORY'] = str(CACHE / 'objects')


def run(args, **kwargs):
    return subprocess.run(args, env=env, check=True, capture_output=True, **kwargs).stdout


head = run(['git','rev-parse','HEAD']).decode().strip()
export = CACHE / 'task-exports' / head
export.mkdir(parents=True, exist_ok=True)
pack = export / 'incremental.pack'
if not pack.exists():
    with pack.open('xb') as stream:
        subprocess.run(['git','pack-objects','--stdout','--revs'],env=env,
            input=(head+'\n^be2931f0898b49545b3b442b70761416e3a5fc7e\n').encode(),
            stdout=stream,stderr=subprocess.PIPE,check=True)
digest = run(['git','index-pack','--strict',str(pack)]).decode().strip()
assert len(digest)==40 and all(c in '0123456789abcdef' for c in digest)
for source in [pack,pack.with_suffix('.idx')]:
    target = ORIGINAL / 'objects/pack' / ('pack-'+digest+source.suffix)
    if not target.exists():
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
    assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
plain = env.copy()
plain.pop('GIT_OBJECT_DIRECTORY')
subprocess.run(['git','cat-file','-e',head+'^{commit}'],env=plain,check=True)
print('APPENDED_VERIFIED='+head)
