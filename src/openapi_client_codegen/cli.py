import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from typer import Option, Typer

from .client import generate_client
from .downgrade import downgrade_openapi_3_1_to_3_0
from .orchestrator import ClientNaming, ProjectsConfig, SpecProducer
from .templates import regenerate_templates

app = Typer(pretty_exceptions_show_locals=False)


@app.command()
def generate_projects_command(
    config: Annotated[
        Path, Option(help="JSON config carrying the projects mapping, the client identity, and the spec command")
    ],
    project: Annotated[str | None, Option(help="Generate only this project, as keyed in the config")] = None,
    client: Annotated[str | None, Option(help="Generate only this client generator")] = None,
    no_cache: Annotated[
        bool, Option("--no-cache", help="Regenerate even when the committed spec is unchanged")
    ] = False,
    root: Annotated[Path, Option(help="Repository root the project paths resolve against")] = Path(),
) -> None:
    settings = ProjectsConfig.model_validate_json(config.read_text(encoding="utf-8"))
    root = root.resolve()
    dump_spec = SpecProducer(settings.spec_command, env=settings.spec_env)

    with TemporaryDirectory() as templates_directory_string:
        templates_directory = Path(templates_directory_string)
        regenerate_templates(templates_directory)

        for project_name, clients in settings.projects.items():
            if project is not None and project != project_name:
                continue

            project_directory = root / project_name
            print(f"Producing OpenAPI spec for project: {project_directory}")

            openapi_json = json.loads(dump_spec(project_directory))
            downgrade_openapi_3_1_to_3_0(openapi_json)
            openapi_spec = json.dumps(openapi_json, indent=2)

            spec_path = project_directory / "openapi.json"

            if spec_path.exists():
                old_spec = spec_path.read_text(encoding="utf-8")

                if openapi_spec == old_spec and not no_cache:
                    print("OpenAPI spec unchanged, skipping client generation")
                    continue

            spec_path.write_text(openapi_spec, encoding="utf-8")

            base = f"{project_name.rsplit('/', maxsplit=1)[-1]}-client"
            dashed = f"{settings.root_name}-{base}"
            names = ClientNaming(
                base=base,
                dashed=dashed,
                underscored=dashed.replace("-", "_"),
                camel=f"{settings.root_name.capitalize()}{''.join(part.capitalize() for part in base.split('-'))}",
            )

            for client_name in clients:
                if client is not None and client_name != client:
                    continue

                generate_client(
                    openapi_spec,
                    client_name,
                    settings.generated_root / client_name / names.base,
                    names,
                    templates_dir=templates_directory,
                    npm_scope=settings.npm_scope,
                    license_spdx=settings.license_spdx,
                    repository_url=settings.repository_url,
                )
