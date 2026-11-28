"""Discover filesystem Skill packages and load their contents on demand."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.observability.tracing import span
from app.skills.loader import (
    MAX_RESOURCE_BYTES,
    MAX_WORKFLOW_BYTES,
    SKILLS_DIR,
    is_link,
    package_file,
    read_frontmatter,
    read_instructions,
    read_json_object,
    read_text_file,
    resource_parts,
)
from app.skills.schemas import (
    SkillFrontmatter,
    SkillLoadError,
    SkillMetadata,
    SkillResource,
    skill_metadata,
)


class SkillRegistry:
    def __init__(self, root: Path = SKILLS_DIR) -> None:
        self._root = root.resolve()
        self._metadata: dict[str, SkillMetadata] = {}
        self._frontmatter: dict[str, SkillFrontmatter] = {}
        self._instructions: dict[str, str] = {}
        self._invalid = 0
        self._discover(root)

    def _discover(self, root: Path) -> None:
        try:
            if is_link(root.lstat()):
                return
            packages = sorted(root.iterdir())
        except OSError:
            return
        for package in packages:
            try:
                header = read_frontmatter(package_file(self._root, package.name, "SKILL.md"))
                if header.name != package.name:
                    raise SkillLoadError("Skill name must match the package directory")
                resource_map = read_json_object(header.metadata.get("adaptive-resources", "{}"))
                resources = []
                for path, purpose in resource_map.items():
                    resource_parts(path)
                    if not isinstance(purpose, str) or not purpose.strip():
                        raise SkillLoadError("Missing resource purpose")
                    resources.append(SkillResource(path=path, purpose=purpose))
                try:
                    (package / "workflow.json").lstat()
                    has_workflow = True
                except FileNotFoundError:
                    has_workflow = False
                self._metadata[header.name] = skill_metadata(
                    header, tuple(resources), has_workflow=has_workflow
                )
                self._frontmatter[header.name] = header
            except (FileNotFoundError, NotADirectoryError):
                continue
            except (ValueError, OSError):
                self._invalid += 1

    def metadata(self) -> tuple[SkillMetadata, ...]:
        with span(
            "skill.discovery",
            skill_names=tuple(self._metadata),
            count=len(self._metadata),
            skill_invalid_count=self._invalid,
        ):
            return tuple(self._metadata.values())

    def get(self, name: str) -> SkillMetadata | None:
        return self._metadata.get(name)

    def load_instructions(self, name: str) -> str:
        if name not in self._metadata:
            raise SkillLoadError("Unknown skill package")
        cache_hit = name in self._instructions
        with span("skill.instructions", skill_name=name, cache_hit=cache_hit) as event:
            if not cache_hit:
                path = self._file(name, "SKILL.md")
                self._instructions[name] = read_instructions(path, self._frontmatter[name])
            body = self._instructions[name]
            if event is not None:
                event.metadata["count"] = len(body.encode("utf-8"))
            return body

    def load_workflow(self, name: str) -> dict[str, Any] | None:
        metadata = self._metadata_for(name)
        if not metadata.has_workflow:
            return None
        with span("skill.workflow_load", skill_name=name) as event:
            raw = read_text_file(self._file(name, "workflow.json"), MAX_WORKFLOW_BYTES)
            if event is not None:
                event.metadata["count"] = len(raw.encode("utf-8"))
            return read_json_object(raw)

    def load_resource(self, name: str, relative_path: str) -> str:
        metadata = self._metadata_for(name)
        parts = resource_parts(relative_path)
        if all(relative_path != resource.path for resource in metadata.resources):
            raise SkillLoadError("Undeclared skill resource")
        with span("skill.resource", skill_name=name, skill_resource=relative_path) as event:
            body = read_text_file(self._file(name, *parts), MAX_RESOURCE_BYTES)
            if event is not None:
                event.metadata["count"] = len(body.encode("utf-8"))
            return body

    def _metadata_for(self, name: str) -> SkillMetadata:
        result = self.get(name)
        if result is None:
            raise SkillLoadError("Unknown skill package")
        return result

    def _file(self, name: str, *parts: str) -> Path:
        try:
            return package_file(self._root, name, *parts)
        except OSError as error:
            raise SkillLoadError("Skill file is unavailable") from error


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
