from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from bashrun.bash import bash_output

from .client import generate_client
from .downgrade import downgrade_openapi_3_1_to_3_0
from .naming import DefaultNamingPolicy
from .templates import regenerate_templates


class SpecProducer:
    def __init__(self, command: str) -> None:
        self.command = command

    def __call__(self, project: Path) -> str:
        return bash_output(self.command, cwd=project)


def generate_projects(
    projects: dict[str, list[str]],
    root_name: str,
    generated_root: Path,
    dump_spec: Callable[[Path], str],
    npm_scope: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
    project: str | None = None,
    client: str | None = None,
    no_cache: bool = False,
    root: Path = Path(),
) -> None:
    root = root.resolve()
    naming = DefaultNamingPolicy(root_name)

    with TemporaryDirectory() as templates_directory_string:
        templates_directory = Path(templates_directory_string)
        regenerate_templates(templates_directory)

        for project_name, clients in projects.items():
            if project is not None and project != project_name:
                continue

            openapi_spec = _produce_and_cache_spec(root / project_name, dump_spec, no_cache)

            if openapi_spec is None:
                continue

            names = naming(project_name)

            for client_name in clients:
                if client is not None and client_name != client:
                    continue

                generate_client(
                    openapi_spec,
                    client_name,
                    generated_root / client_name / names.base,
                    names,
                    templates_dir=templates_directory,
                    npm_scope=npm_scope,
                    license_spdx=license_spdx,
                    repository_url=repository_url,
                )


def dump_openapi_spec(project: Path) -> str:
    # CODEGEN=1 gates a service package's heavy imports so the app imports cleanly for the spec
    # dump; it reaches the child through bashrun's per-call env overlay.
    return bash_output("uv run --project . python -m src.dump_openapi", cwd=project, env={"CODEGEN": "1"})


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
