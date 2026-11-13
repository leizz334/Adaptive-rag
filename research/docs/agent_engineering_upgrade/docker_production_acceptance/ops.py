"""Local deployment evidence helper. Never prints credential material."""

import base64
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LINUX_ROOT = "/mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation"


def wsl(code, timeout=120):
    encoded = base64.b64encode(code.encode()).decode()
    result = subprocess.run(
        [
            "wsl",
            "-d",
            "Ubuntu-24.04",
            "-u",
            "root",
            "--",
            "python3",
            "-c",
            f'import base64;exec(base64.b64decode("{encoded}"))',
        ],
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode:
        # Commands must explicitly sanitize stdout; suppress noisy WSL stderr.
        raise RuntimeError(result.stdout.decode("utf8", errors="replace")[-3000:])
    return result.stdout.decode("utf8")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        prefix = (
            "import os,sys;os.chdir(" + repr(LINUX_ROOT) + ");sys.argv=" + repr(sys.argv[2:]) + "\n"
        )
        print(wsl(prefix + Path(sys.argv[2]).read_text(encoding="utf8"), timeout=3600))
    elif sys.argv[1] == "inventory":
        code = """
import subprocess,json
ids=subprocess.check_output(['docker','ps','-aq'],text=True).split()
rows=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
out=[]
for r in rows:
 labels=r['Config'].get('Labels',{})
 out.append(dict(id=r['Id'],name=r['Name'],image=r['Image'],image_ref=r['Config']['Image'],status=r['State']['Status'],health=r['State'].get('Health',{}).get('Status'),started=r['State']['StartedAt'],project=labels.get('com.docker.compose.project'),service=labels.get('com.docker.compose.service'),config_files=labels.get('com.docker.compose.project.config_files'),ports=r['HostConfig']['PortBindings'],mounts=[{k:m.get(k) for k in ['Type','Name','Destination','RW']} for m in r['Mounts']]))
print(json.dumps(out,indent=2))
"""
        output = wsl(code)
        target = HERE / "evidence" / "before-containers.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf8") as stream:
            stream.write(output)
        for row in json.loads(output):
            print(row["name"], row["status"], row["image"][:20], row["ports"])
