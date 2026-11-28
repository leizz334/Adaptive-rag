"""Standard Agent Skills frontmatter and the local capability metadata."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import IntentLabel
from app.schemas.goals import GoalKind

SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*")


class SkillLoadError(ValueError):
    """The package or resource cannot be loaded within the Skill Runtime boundary."""


class SkillFrontmatter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = None
    compatibility: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict[str, str] = Field(default_factory=dict)
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not SKILL_NAME.fullmatch(value):
            raise ValueError("Invalid Agent Skills name")
        return value

    @field_validator("description", "compatibility")
    @classmethod
    def reject_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Blank Agent Skills metadata value")
        return value


@dataclass(frozen=True)
class SkillResource:
    path: str
    purpose: str


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    intents: tuple[str, ...]
    goals: tuple[GoalKind, ...]
    tools: tuple[str, ...]
    resources: tuple[SkillResource, ...]
    has_workflow: bool
    extensions: Mapping[str, str]


def extension_values(
    extensions: Mapping[str, str], key: str, separator: str = ","
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value.strip() for value in extensions.get(key, "").split(separator) if value.strip()
        )
    )


def skill_metadata(
    frontmatter: SkillFrontmatter, resources: tuple[SkillResource, ...], *, has_workflow: bool
) -> SkillMetadata:
    extensions = frontmatter.metadata
    tools = extension_values(extensions, "adaptive-tools")
    if any(not TOOL_NAME.fullmatch(name) for name in tools):
        raise SkillLoadError("Invalid registered tool candidate name")
    return SkillMetadata(
        name=frontmatter.name,
        description=frontmatter.description,
        intents=tuple(
            IntentLabel(value).value for value in extension_values(extensions, "adaptive-intents")
        ),
        goals=tuple(GoalKind(value) for value in extension_values(extensions, "adaptive-goals")),
        tools=tools,
        resources=resources,
        has_workflow=has_workflow,
        extensions=MappingProxyType(dict(extensions)),
    )
