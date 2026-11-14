"""Execute named phase actions in WSL; retain unsanitized diagnostics privately."""

import sys

from research.docs.agent_engineering_upgrade.docker_production_acceptance.ops import wsl

assert sys.argv[1] in {"environment", "acceptance", "regression"}
root = "/mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation"
argv = [
    "/home/panda/.venvs/adaptive-rag-workbench/bin/python",
    "-m",
    "research.docs.agent_engineering_upgrade.deepseek_business_acceptance." + sys.argv[1],
    *sys.argv[2:],
]
code = """
import os,subprocess,json
from pathlib import Path
os.umask(0o077)
private=Path('/home/panda/.adaptive-rag-business-20261114')
private.mkdir(exist_ok=True,mode=0o700)
os.chown(private,1000,1000)
p=subprocess.run(ARGS,cwd=ROOT,capture_output=True,text=True)
if p.returncode:
 (private/'last-error.log').write_text(p.stderr)
print(p.stdout)
print('PHASE_EXIT='+str(p.returncode))
""".replace("ARGS", repr(argv)).replace("ROOT", repr(root))
print(wsl(code, timeout=3600))
