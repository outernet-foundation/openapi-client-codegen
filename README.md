# openapi-clientgen

Generate typed API clients from an OpenAPI schema. `openapi-clientgen` wraps [OpenAPI Generator](https://openapi-generator.tech/): it downgrades OpenAPI 3.1→3.0 (the generator only accepts 3.0), authors and patches the C# templates, runs the generator, and writes Unity package metadata. It produces a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client.

The generic steps live here; the caller supplies the OpenAPI spec, the project→client mapping, the package-name policy, and the output paths. See [`AGENTS.md`](./AGENTS.md) for the API surface, the lib-owns/consumer-owns boundary, and the patch mechanism.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- **Java (JDK 11+)** and **`uvx`** on PATH at runtime — the generator runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`

## CLI

A thin CLI exposes the OpenAPI 3.1→3.0 downgrade as a standalone step:

```bash
uv run openapi-clientgen path/to/openapi.json            # downgrade in place
uv run openapi-clientgen path/to/openapi.json out.json   # write elsewhere
```

Client generation itself is driven from Python (it needs the consumer's project map, naming policy, and output paths):

```python
import json
import tempfile
from pathlib import Path

from openapi_clientgen import (
    DefaultNamingPolicy,
    downgrade_openapi_3_1_to_3_0,
    generate_client,
    regenerate_templates,
)

naming = DefaultNamingPolicy("myproject")
templates_dir = Path(tempfile.mkdtemp())
regenerate_templates(templates_dir)

# Produce the raw OpenAPI JSON however your app exposes it, then downgrade it.
schema = json.loads(my_openapi_spec_json())
downgrade_openapi_3_1_to_3_0(schema)
spec = json.dumps(schema, indent=2)

generate_client(spec, "python", Path("generated/python/api-client"), naming("services/api"))
generate_client(
    spec, "csharp", Path("generated/csharp/api-client"), naming("services/api"), templates_dir=templates_dir
)
```

## Consuming from another repo

git-reference the package and declare `bashrun`'s source alongside it (uv's `[tool.uv.sources]` are not transitive):

```toml
[project]
dependencies = ["openapi-clientgen"]

[tool.uv.sources]
openapi-clientgen = { git = "https://github.com/outernet-foundation/openapi-clientgen.git", rev = "<pin-a-commit-sha>" }
bashrun = { git = "https://github.com/outernet-foundation/bashrun.git", rev = "<pin-a-commit-sha>" }
```

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pytest
```
