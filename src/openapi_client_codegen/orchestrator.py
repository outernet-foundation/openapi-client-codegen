from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from pathlib import Path

from bashrun.bash import bash_output
from packaging.specifiers import SpecifierSet
from pydantic import BaseModel, ConfigDict, field_validator
from strictyaml import load as load_strict_yaml

DEV_SENTINEL = "0.0.0.dev0"


class ProjectsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: dict[str, list[str]]
    root_name: str
    generated_root: Path
    spec_command: str
    spec_env: dict[str, str] | None = None
    npm_scope: str | None = None
    license_spdx: str | None = None
    repository_url: str | None = None
    requires: str | None = None

    @field_validator("requires")
    @classmethod
    def validate_requires(cls, value: str | None) -> str | None:
        if not value:
            return None
        SpecifierSet(value)
        return value


@dataclass(frozen=True)
class ClientNaming:
    base: str
    dashed: str
    underscored: str
    camel: str


class SpecProducer:
    def __init__(self, command: str, env: dict[str, str] | None = None) -> None:
        self.command = command
        self.env = env

    def __call__(self, project: Path) -> str:
        return bash_output(self.command, cwd=project, env=self.env)


def load_config(path: Path) -> ProjectsConfig:
    config = ProjectsConfig.model_validate(load_strict_yaml(path.read_text(encoding="utf-8")).data)
    if config.requires is None:
        return config
    installed = importlib.metadata.version("openapi-client-codegen")
    if installed == DEV_SENTINEL:
        return config
    if not SpecifierSet(config.requires).contains(installed, prereleases=True):
        raise SystemExit(f"openapi-client-codegen {installed} does not satisfy requires={config.requires!r}")
    return config
