import json
from pathlib import Path
from typing import Annotated

from typer import Argument, Typer

from .downgrade import downgrade_openapi_3_1_to_3_0

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
