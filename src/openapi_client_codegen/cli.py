import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from typer import Argument, Option, Typer

from .client import generate_client
from .downgrade import downgrade_openapi_3_1_to_3_0
from .naming import DefaultNamingPolicy
from .templates import regenerate_templates

app = Typer(pretty_exceptions_show_locals=False)


@app.command()
def downgrade(
    input_file: Annotated[Path, Argument(help="OpenAPI 3.1 JSON to downgrade to 3.0.3")],
    output_file: Annotated[Path | None, Argument(help="Write here instead of overwriting input_file")] = None,
) -> None:
    schema = json.loads(input_file.read_text(encoding="utf-8"))
    downgrade_openapi_3_1_to_3_0(schema)
    destination = output_file if output_file is not None else input_file
    destination.write_text(json.dumps(schema, indent=2), encoding="utf-8")


@app.command()
def generate(
    spec_file: Annotated[Path, Argument(help="OpenAPI 3.0 spec JSON to generate from")],
    output_dir: Annotated[Path, Argument(help="Directory to sync the generated client into")],
    root_name: Annotated[str, Option(help="Root name handed to DefaultNamingPolicy")],
    project: Annotated[str, Option(help="Project path; its last segment names the client")],
    generator: Annotated[str, Option(help="openapi-generator generator name")] = "csharp",
    npm_scope: Annotated[str | None, Option(help="npm scope composing the UPM package identity")] = None,
    license_spdx: Annotated[str | None, Option(help="SPDX license id written to package.json")] = None,
    repository_url: Annotated[str | None, Option(help="git repository URL written to package.json")] = None,
) -> None:
    with TemporaryDirectory() as templates_directory_string:
        templates_directory = Path(templates_directory_string)
        templates_dir = templates_directory if generator == "csharp" else None
        if templates_dir is not None:
            regenerate_templates(templates_dir)

        generate_client(
            spec_file.read_text(encoding="utf-8"),
            generator,
            output_dir,
            DefaultNamingPolicy(root_name)(project),
            templates_dir=templates_dir,
            npm_scope=npm_scope,
            license_spdx=license_spdx,
            repository_url=repository_url,
        )
