"""Run only named phase scripts in the existing WSL dev Python, without secret output."""
import base64
import json
from pathlib import Path
import sys

from research.docs.agent_engineering_upgrade.docker_production_acceptance.ops import wsl

name=sys.argv[1]
assert name in {'prepare','live','checks','dryrun','finish'}
root='/mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation'
script=root+'/research/docs/agent_engineering_upgrade/deepseek_live_acceptance/'+name+'.py'
arguments=sys.argv[2:]
code='''
import subprocess,json,os
from pathlib import Path
os.umask(0o077)
private=Path('/home/panda/.adaptive-rag-live-20261114')
private.mkdir(exist_ok=True,mode=0o700)
os.chown(private,1000,1000)
result=subprocess.run(ARGS,cwd=ROOT,capture_output=True,text=True)
if result.returncode:
 (private/'last-script-error.log').write_text(result.stderr)
print(result.stdout)
print('PHASE_SCRIPT_EXIT='+str(result.returncode))
'''.replace('ARGS',repr(['/home/panda/.venvs/adaptive-rag-workbench/bin/python',script,*arguments])).replace('ROOT',repr(root))
print(wsl(code,timeout=3600))
