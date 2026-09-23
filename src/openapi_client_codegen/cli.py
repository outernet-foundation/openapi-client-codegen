from pathlib import Path
from typing import Annotated

from pydantic import ValidationError
from typer import BadParameter, Option, Typer

from .orchestrator import ProjectsConfig, generate_projects

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
    try:
        settings = ProjectsConfig.model_validate_json(config.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise BadParameter(str(error)) from error

    generate_projects(settings, project=project, client=client, no_cache=no_cache, root=root)
