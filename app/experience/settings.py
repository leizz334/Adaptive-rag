"""Independent offline configuration; business settings/source remain frozen."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ExperienceSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None)
    experience_memory_mode: Literal["off", "shadow"] = "off"
