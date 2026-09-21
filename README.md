# openapi-clientgen

Generate typed API clients from an OpenAPI schema. `openapi-clientgen` wraps [OpenAPI Generator](https://openapi-generator.tech/): it downgrades OpenAPI 3.1→3.0 (the generator only accepts 3.0), authors and patches the C# templates, runs the generator, and writes Unity package metadata. It produces a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client.

The generic steps live here; the caller supplies the OpenAPI spec, the project→client mapping, the package-name policy, and the output paths. See [`AGENTS.md`](./AGENTS.md) for the API surface, the lib-owns/consumer-owns boundary, and the patch mechanism.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- **Java (JDK 11+)** and **`uvx`** on PATH at runtime — the generator runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`

## CLI

A thin CLI exposes the OpenAPI 3.1→3.0 downgrade and single-client generation:

```bash
uv run openapi-clientgen downgrade path/to/openapi.json            # 3.1→3.0 in place
uv run openapi-clientgen downgrade path/to/openapi.json out.json   # write elsewhere

uv run openapi-clientgen generate path/to/openapi.json generated/csharp/api-client \
  --root-name myproject --project services/api \
  --npm-scope org.example.myproject --license-spdx Apache-2.0 \
  --repository-url https://github.com/org/repo.git
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

Install from PyPI:

```toml
[project]
dependencies = ["openapi-clientgen>=0.1.0"]
```

`bashrun` resolves transitively. At **runtime** the generator also needs Java (JDK 11+) and `uvx` on PATH. To test an unreleased change, pin the repo at a git ref in a scratch branch instead (`openapi-clientgen = { git = "…", rev = "<sha>" }` under `[tool.uv.sources]`) and drop the pin when the release lands.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pytest
```
