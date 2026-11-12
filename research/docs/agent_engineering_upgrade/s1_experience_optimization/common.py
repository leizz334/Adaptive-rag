import hashlib
import json
from pathlib import Path

from app.experience.contracts import EvidenceRef, ExperienceScope

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
RUN = HERE / "runs/ubuntu_EX_20261112_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def read(path):
    return json.loads(Path(path).read_text())


def ref(path, kind="evaluation", pointer=""):
    p = Path(path).resolve()
    return EvidenceRef(
        artifact=p.relative_to(STATE).as_posix(), sha256=sha(p), pointer=pointer, kind=kind
    )


def scope_for(session):
    return ExperienceScope(
        tenant_ref=hashlib.sha256(b"s1ex_owned_synthetic_tenant").hexdigest(),
        user_ref=hashlib.sha256(b"s1ex_probe_user").hexdigest(),
        session_ref=hashlib.sha256(session.encode()).hexdigest(),
        verified=True,
    )


def verify_freeze():
    frozen = read(HERE / "freeze.json")
    if any(sha(ROOT / p) != h for p, h in frozen["hashes"].items()):
        raise RuntimeError("EX frozen source/data/scorer drift blocks paid dispatch")
    from importlib.metadata import version

    if any(version(name) != expected for name, expected in frozen.get("packages", {}).items()):
        raise RuntimeError("EX dependency drift blocks paid dispatch")
    if sha(HERE / ".private/experience.sqlite3") != frozen["experience_sqlite_sha256"]:
        raise RuntimeError("EX qualification store drift blocks paid dispatch")
    return frozen
