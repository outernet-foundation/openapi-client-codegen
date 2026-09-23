from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from bashrun.bash import bash_output
from pydantic import BaseModel, ConfigDict

from .client import generate_client
from .downgrade import downgrade_openapi_3_1_to_3_0
from .templates import regenerate_templates


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


def generate_projects(
    config: ProjectsConfig,
    project: str | None = None,
    client: str | None = None,
    no_cache: bool = False,
    root: Path = Path(),
) -> None:
    root = root.resolve()
    dump_spec = SpecProducer(config.spec_command, env=config.spec_env)

    with TemporaryDirectory() as templates_directory_string:
        templates_directory = Path(templates_directory_string)
        regenerate_templates(templates_directory)

        for project_name, clients in config.projects.items():
            if project is not None and project != project_name:
                continue

            openapi_spec = _produce_and_cache_spec(root / project_name, dump_spec, no_cache)

            if openapi_spec is None:
                continue

            base = f"{project_name.rsplit('/', maxsplit=1)[-1]}-client"
            dashed = f"{config.root_name}-{base}"
            names = ClientNaming(
                base=base,
                dashed=dashed,
                underscored=dashed.replace("-", "_"),
                camel=f"{config.root_name.capitalize()}{''.join(part.capitalize() for part in base.split('-'))}",
            )

            for client_name in clients:
                if client is not None and client_name != client:
                    continue

                generate_client(
                    openapi_spec,
                    client_name,
                    config.generated_root / client_name / names.base,
                    names,
                    templates_dir=templates_directory,
                    npm_scope=config.npm_scope,
                    license_spdx=config.license_spdx,
                    repository_url=config.repository_url,
                )


def _produce_and_cache_spec(project: Path, dump_spec: Callable[[Path], str], no_cache: bool) -> str | None:
    print(f"Producing OpenAPI spec for project: {project}")

    openapi_json = json.loads(dump_spec(project))
    downgrade_openapi_3_1_to_3_0(openapi_json)
    openapi_spec = json.dumps(openapi_json, indent=2)

    spec_path = project / "openapi.json"

    if spec_path.exists():
        old_spec = spec_path.read_text(encoding="utf-8")

        if openapi_spec == old_spec and not no_cache:
            print("OpenAPI spec unchanged, skipping client generation")
            return None

    spec_path.write_text(openapi_spec, encoding="utf-8")

    return openapi_spec
