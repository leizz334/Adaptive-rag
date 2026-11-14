"""API-only reversible Offline deployment; no RealDev container is started."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from research.docs.agent_engineering_upgrade.docker_production_acceptance import deploy as previous

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/agent_usability"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-usability-20261114")
IMAGE = "adaptive-rag-production:usability-20261114"
ROLLBACK = "adaptive-rag-production:rollback-usability-20261114"
os.umask(0o077)
previous.PRIVATE = PRIVATE
previous.EVIDENCE = OUT


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, indent=2)


if sys.argv[1] == "build":
    with (PRIVATE / "image-build.log").open("x") as log:
        result = subprocess.run(
            ["docker", "build", "--target", "showcase", "-t", IMAGE, "."], stdout=log, stderr=log
        )
    assert result.returncode == 0, "Image build failed; private log retained"
    image = previous.run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
    save("P3-image.json", {"image": IMAGE, "image_id": image, "build_exit": 0, "paid_requests": 0})
    print(json.dumps({"build": "PASS", "image_id": image}))
elif sys.argv[1] == "refresh":
    base = "adaptive-rag-production:usability-base-20261114"
    base_id = json.loads((OUT / "P3-image.json").read_text())["image_id"]
    assert (
        previous.run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}").strip() == base_id
    )
    previous.run("docker", "tag", base_id, base)
    context = PRIVATE / "refresh-context"
    context.mkdir()  # Never include .env, private credentials, or repository metadata.
    shutil.copytree(
        ROOT / "app", context / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copytree(ROOT / "frontend/dist", context / "frontend/dist")
    shutil.copyfile(HERE / "Dockerfile.refresh", context / "Dockerfile")
    with (PRIVATE / "image-refresh.log").open("x") as log:
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE, str(context)], stdout=log, stderr=log
        )
    assert result.returncode == 0, "Image refresh failed; private log retained"
    image = previous.run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
    save(
        "P3-image-final.json",
        {
            "image": IMAGE,
            "image_id": image,
            "dependency_base_id": base_id,
            "build_exit": 0,
            "context": "app and built frontend only; no credentials",
            "paid_requests": 0,
        },
    )
    print(json.dumps({"refresh": "PASS", "image_id": image}))
elif sys.argv[1] == "prepare":
    assert json.loads((OUT / "P2-mock-acceptance.json").read_text())["paid_provider_requests"] == 0
    frontend = json.loads((OUT / "P3-frontend.json").read_text())
    assert all(
        frontend[key]["status"] == "PASS"
        for key in ["unit_validation", "typecheck", "production_build"]
    )
    row = json.loads(previous.run("docker", "inspect", "adaptive-rag-showcase-api-1"))[0]
    before = json.loads((OUT / "baseline.json").read_text())
    original = next(r for r in before["containers"] if r["name"] == "/adaptive-rag-showcase-api-1")
    assert row["Id"] == original["id"] and row["Image"] == original["image"]
    (PRIVATE / "original-api-inspect.json").write_text(json.dumps(row))
    previous.run("docker", "tag", row["Image"], ROLLBACK)
    dump = previous.run(
        "docker",
        "exec",
        "adaptive-rag-showcase-postgres-1",
        "pg_dump",
        "-U",
        "adaptive",
        "-d",
        "adaptive_showcase",
        "--format=custom",
        binary=True,
    )
    with (PRIVATE / "postgres-before.dump").open("xb") as stream:
        stream.write(dump)
    (PRIVATE / "rollback.json").write_text(json.dumps({"services": {"api": {"image": ROLLBACK}}}))
    (PRIVATE / "upgrade.json").write_text(
        json.dumps({"services": {"api": {"image": IMAGE, "pull_policy": "never"}}})
    )
    save("before-data.json", previous.fingerprint())
    save(
        "rollback.json",
        {
            "old_image_id": row["Image"],
            "rollback_tag": ROLLBACK,
            "private_directory": str(PRIVATE),
            "database_backup": str(PRIVATE / "postgres-before.dump"),
            "api_only": True,
            "migration_seed_not_run": True,
        },
    )
    print(
        json.dumps(
            {"prepare": "PASS", "rollback_image": row["Image"], "data_backup_bytes": len(dump)}
        )
    )
elif sys.argv[1] == "upgrade":
    os.environ["SHOWCASE_PORT"] = "8000"
    previous.upgrade_api()  # Existing reviewed rollback-on-exception/health verification.
elif sys.argv[1] == "fixture":
    code = """
import asyncio,json,time
from datetime import datetime,UTC
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.demo.docker import runtime_settings
from app.repositories.models import OrderRow,OrderItemRow
async def main():
 engine=create_async_engine(runtime_settings().database_url)
 identifier='ORD'+str(int(time.time()*1000))
 try:
  async with async_sessionmaker(engine)() as db:
   async with db.begin():
    assert await db.get(OrderRow,identifier) is None
    now=datetime.now(UTC)
    db.add(OrderRow(order_id=identifier,user_id='web_demo_a',status='paid',total_cents=6800,created_at=now,paid_at=now))
    await db.flush()
    db.add(OrderItemRow(order_id=identifier,sku='SKU-WEB-BAG',name='演示帆布包',quantity=2,unit_price_cents=3400,customized=False))
  print(json.dumps({'synthetic_cancel_order':identifier,'existing_orders_modified':False}))
 finally:await engine.dispose()
asyncio.run(main())
"""
    result = json.loads(
        previous.run("docker", "exec", "adaptive-rag-showcase-api-1", "python", "-c", code)
    )
    save("P3-browser-fixture.json", result)
    print(json.dumps(result))
