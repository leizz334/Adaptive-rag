"""Bounded Skill package reads and the compatibility view for older callers."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import yaml

from app.skills.schemas import SkillFrontmatter, SkillLoadError, SkillMetadata, extension_values

SKILLS_DIR = Path(__file__).parent / "definitions"
MAX_FRONTMATTER_BYTES = 8_192
MAX_INSTRUCTION_BYTES = 48 * 1024
MAX_WORKFLOW_BYTES = 16 * 1024
MAX_RESOURCE_BYTES = 8_192
_RESOURCE_SUFFIXES = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
_PATH_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


class _UniqueYamlLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise SkillLoadError("Duplicate YAML metadata key")
        return mapping


def is_link(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def package_file(root: Path, *parts: str) -> Path:
    """Inspect each path component without following its final symlink or reparse point."""
    if is_link(root.lstat()):
        raise SkillLoadError("Linked skill package root is forbidden")
    path = root
    info = None
    for part in parts:
        path = path / part
        info = path.lstat()
        if is_link(info):
            raise SkillLoadError("Linked skill paths are forbidden")
    if (
        info is None
        or not stat.S_ISREG(info.st_mode)
        or not path.resolve(strict=True).is_relative_to(root)
    ):
        raise SkillLoadError("Invalid skill file")
    return path


def resource_parts(relative_path: str) -> tuple[str, ...]:
    path = PurePosixPath(relative_path)
    if (
        path.as_posix() != relative_path
        or len(path.parts) < 2
        or path.parts[0] not in {"references", "assets"}
        or path.suffix.lower() not in _RESOURCE_SUFFIXES
        or any(not _PATH_COMPONENT.fullmatch(part) or part.endswith(".") for part in path.parts)
    ):
        raise SkillLoadError("Invalid skill resource path")
    return path.parts


def _decode(data: bytes) -> str:
    if b"\0" in data:
        raise SkillLoadError("Non-text skill file")
    return data.decode("utf-8-sig").replace("\r\n", "\n")


def _frontmatter(stream: BinaryIO) -> SkillFrontmatter:
    first = stream.readline(8)
    if first.removeprefix(b"\xef\xbb\xbf").rstrip(b"\r\n") != b"---":
        raise SkillLoadError("Missing YAML frontmatter")
    remaining = MAX_FRONTMATTER_BYTES - len(first)
    lines: list[bytes] = []
    while remaining > 0:
        line = stream.readline(remaining + 1)
        remaining -= len(line)
        if not line or remaining < 0:
            break
        if line.rstrip(b"\r\n") == b"---":
            raw = _decode(b"".join(lines))
            if any(
                isinstance(token, yaml.tokens.AnchorToken | yaml.tokens.AliasToken)
                for token in yaml.scan(raw)
            ):
                raise SkillLoadError("YAML anchors and aliases are forbidden")
            return SkillFrontmatter.model_validate(yaml.load(raw, Loader=_UniqueYamlLoader))
        lines.append(line)
    raise SkillLoadError("Skill frontmatter is unclosed or too large")


def read_frontmatter(path: Path) -> SkillFrontmatter:
    try:
        with path.open("rb") as stream:
            return _frontmatter(stream)
    except (OSError, ValueError, yaml.YAMLError, RecursionError) as error:
        raise SkillLoadError("Invalid skill frontmatter") from error


def _read_text(stream: BinaryIO, limit: int) -> str:
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise SkillLoadError("Skill file exceeds its size limit")
    return _decode(data)


def read_instructions(path: Path, expected: SkillFrontmatter) -> str:
    try:
        with path.open("rb") as stream:
            if _frontmatter(stream) != expected:
                raise SkillLoadError("Skill metadata changed after discovery")
            body = _read_text(stream, MAX_INSTRUCTION_BYTES)
            if not body.strip():
                raise SkillLoadError("Missing skill instructions")
            return body
    except (OSError, ValueError, yaml.YAMLError, RecursionError) as error:
        raise SkillLoadError("Invalid skill instructions") from error


def read_text_file(path: Path, limit: int) -> str:
    try:
        with path.open("rb") as stream:
            return _read_text(stream, limit)
    except (OSError, ValueError) as error:
        raise SkillLoadError("Invalid skill file") from error


def read_json_object(raw: str) -> dict[str, Any]:
    def pairs(items):
        result = dict(items)
        if len(result) != len(items):
            raise SkillLoadError("Duplicate skill JSON key")
        return result

    def invalid_constant(_value):
        raise SkillLoadError("Non-finite skill JSON value")

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as error:
        raise SkillLoadError("Invalid skill JSON") from error
    if not isinstance(result, dict):
        raise SkillLoadError("Skill JSON must be an object")
    return result


def _legacy_steps(instructions: str) -> list[str]:
    _, _, section = instructions.partition("## Steps\n")
    steps = section.split("\n## ", 1)[0]
    return [line.removeprefix("- ") for line in steps.splitlines() if line.startswith("- ")]


def _legacy_record(metadata: SkillMetadata, instructions: str) -> dict:
    return {
        "name": metadata.extensions["adaptive-legacy-name"],
        "description": metadata.extensions.get("adaptive-legacy-description", metadata.description),
        "triggers": list(extension_values(metadata.extensions, "adaptive-legacy-triggers", "|")),
        "steps": _legacy_steps(instructions),
        "tools": list(metadata.tools),
    }


def load_skills() -> list[dict]:
    """Return the original administration and historical replay payload shape."""
    from app.skills.registry import get_skill_registry

    registry = get_skill_registry()
    return [
        _legacy_record(metadata, registry.load_instructions(metadata.name))
        for metadata in registry.metadata()
        if "adaptive-legacy-name" in metadata.extensions
    ]


def skill_by_name(name: str) -> dict | None:
    from app.skills.registry import get_skill_registry

    registry = get_skill_registry()
    for metadata in registry.metadata():
        if metadata.extensions.get("adaptive-legacy-name") == name:
            return _legacy_record(metadata, registry.load_instructions(metadata.name))
    return None


def match_skill(query: str, intent_label: str = "") -> dict | None:
    """Reproduce selection for legacy offline fallbacks and archived evaluations."""
    from app.skills.registry import get_skill_registry

    registry = get_skill_registry()
    matched = None
    for skill in registry.metadata():
        if "adaptive-legacy-name" not in skill.extensions:
            continue
        if any(
            trigger in query
            for trigger in extension_values(skill.extensions, "adaptive-legacy-triggers", "|")
        ):
            matched = skill
            break
        if intent_label in extension_values(skill.extensions, "adaptive-legacy-intents"):
            matched = skill
    if matched is None:
        return None
    return _legacy_record(matched, registry.load_instructions(matched.name))
