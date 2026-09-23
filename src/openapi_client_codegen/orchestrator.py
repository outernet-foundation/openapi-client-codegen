from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bashrun.bash import bash_output
from pydantic import BaseModel, ConfigDict


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
