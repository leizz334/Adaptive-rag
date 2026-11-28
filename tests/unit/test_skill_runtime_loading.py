import os
import subprocess
from pathlib import Path

import pytest

from app.schemas.goals import GoalKind
from app.skills.loader import SkillLoadError, load_skills
from app.skills.registry import SkillRegistry, get_skill_registry


def write_package(root: Path, name: str, frontmatter: str, body: bytes = b"Instructions") -> Path:
    package = root / name
    package.mkdir()
    (package / "SKILL.md").write_bytes(f"---\n{frontmatter}\n---\n".encode() + body)
    return package


def test_discovery_reads_only_frontmatter_and_loads_workflow_on_demand(tmp_path: Path) -> None:
    package = write_package(
        tmp_path,
        "read-orders",
        "name: read-orders\ndescription: Read one order.\nmetadata:\n"
        '  adaptive-goals: "order_status"\n  adaptive-tools: "get_order"',
        body=b"\xff\xfe",
    )
    (package / "workflow.json").write_text("invalid JSON", encoding="utf-8")
    registry = SkillRegistry(tmp_path)

    assert [skill.name for skill in registry.metadata()] == ["read-orders"]
    skill = registry.get("read-orders")
    assert skill is not None
    assert skill.description == "Read one order."
    assert skill.goals == (GoalKind.ORDER_STATUS,)
    assert skill.tools == ("get_order",)
    assert skill.has_workflow
    with pytest.raises(SkillLoadError):
        registry.load_instructions(skill.name)
    with pytest.raises(SkillLoadError):
        registry.load_workflow(skill.name)


def test_discovery_rejects_invalid_spec_and_preserves_valid_packages(tmp_path: Path) -> None:
    write_package(
        tmp_path,
        "valid",
        "name: valid\ndescription: A skill.\nlicense: Apache-2.0\ncompatibility: Adaptive-RAG\n"
        'allowed-tools: "cancel_order Bash"',
    )
    write_package(tmp_path, "mismatch", "name: different\ndescription: Valid description")
    write_package(tmp_path, "double--hyphen", "name: double--hyphen\ndescription: A skill")
    write_package(tmp_path, "duplicate", "name: duplicate\ndescription: A\ndescription: B")
    write_package(tmp_path, "complex", "name: complex\ndescription: Good\nmetadata: {x: [nested]}")
    write_package(tmp_path, "anchor", "name: anchor\ndescription: &ref body\nlicense: *ref")
    write_package(tmp_path, "too-long", f"name: too-long\ndescription: {'x' * 1025}")
    write_package(tmp_path, "empty", "name: empty\ndescription: '   '")
    (tmp_path / "ignored.json").write_text("{}", encoding="utf-8")

    (valid,) = SkillRegistry(tmp_path).metadata()
    assert valid.name == "valid"
    assert valid.tools == ()


def test_instructions_are_cached_after_activation(tmp_path: Path) -> None:
    package = write_package(tmp_path, "demo", "name: demo\ndescription: A skill.")
    registry = SkillRegistry(tmp_path)

    assert registry.load_instructions("demo") == "Instructions"
    (package / "SKILL.md").write_bytes(b"invalid")
    assert registry.load_instructions("demo") == "Instructions"
    assert registry.load_workflow("demo") is None
    assert registry.get("../demo") is None
    with pytest.raises(SkillLoadError):
        registry.load_instructions("../demo")


def test_resources_require_declaration_and_a_bounded_safe_location(tmp_path: Path) -> None:
    package = write_package(
        tmp_path,
        "demo",
        "name: demo\ndescription: A skill.\nmetadata:\n"
        '  adaptive-resources: \'{"references/evidence.md":"tool fields",'
        '"assets/oversize.txt":"examples"}\'',
    )
    references = package / "references"
    references.mkdir()
    (references / "evidence.md").write_text("Evidence", encoding="utf-8")
    (references / "internal.md").write_text("Undeclared", encoding="utf-8")
    assets = package / "assets"
    assets.mkdir()
    (assets / "oversize.txt").write_text("x" * 100_000, encoding="utf-8")
    registry = SkillRegistry(tmp_path)

    assert registry.load_resource("demo", "references/evidence.md") == "Evidence"
    for bad in (
        "references/internal.md",
        "references/../SKILL.md",
        "references\\evidence.md",
        "C:/references/evidence.md",
        "/references/evidence.md",
        "scripts/run.py",
        "assets/oversize.txt",
    ):
        with pytest.raises(SkillLoadError):
            registry.load_resource("demo", bad)


def test_declared_resource_cannot_follow_a_directory_link(tmp_path: Path) -> None:
    package = write_package(
        tmp_path,
        "demo",
        "name: demo\ndescription: A skill.\nmetadata:\n"
        '  adaptive-resources: \'{"references/evidence.md":"tool fields"}\'',
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evidence.md").write_text("Outside", encoding="utf-8")
    link = package / "references"
    if os.name == "nt":
        subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(SkillLoadError):
        SkillRegistry(tmp_path).load_resource("demo", "references/evidence.md")


def test_migrated_packages_and_legacy_view() -> None:
    registry = get_skill_registry()
    assert {skill.name for skill in registry.metadata()} >= {
        "catalog-title-lookup",
        "conditional-order-query",
        "order-cancellation",
        "order-tracking",
        "product-recommend",
        "return-request",
    }
    assert {skill["name"] for skill in load_skills()} == {
        "order_cancellation",
        "order_tracking",
        "product_recommend",
        "return_handling",
    }
    product = registry.get("product-recommend")
    assert product is not None
    assert product.resources[0].path == "references/catalog-evidence.md"
    assert registry.load_resource(product.name, product.resources[0].path)
