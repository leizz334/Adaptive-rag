"""Phase-local WSL runner; diagnostics remain private and no provider Key is read."""
import sys

from research.docs.agent_engineering_upgrade.docker_production_acceptance.ops import wsl

action=sys.argv[1]
assert action in {'mock_environment','acceptance','deploy','verify'}
root='/mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation'
argv=['/home/panda/.venvs/adaptive-rag-workbench/bin/python','-m','research.docs.agent_engineering_upgrade.agent_usability.'+action,*sys.argv[2:]]
source='''
import os,subprocess
from pathlib import Path
os.umask(0o077)
os.chdir(ROOT)
private=Path('/home/panda/.adaptive-rag-usability-20261114')
p=subprocess.run(ARGS,capture_output=True,text=True)
if p.returncode:
 (private/'last-command-error.log').write_text(p.stderr)
print(p.stdout)
print('PHASE_EXIT='+str(p.returncode))
'''.replace('ROOT',repr(root)).replace('ARGS',repr(argv))
print(wsl(source,timeout=3600))
