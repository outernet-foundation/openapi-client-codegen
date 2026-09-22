# openapi-client-codegen

Generate typed API clients from an OpenAPI schema. `openapi-client-codegen` wraps [OpenAPI Generator](https://openapi-generator.tech/): it downgrades OpenAPI 3.1→3.0 (the generator only accepts 3.0), authors and patches the C# templates, runs the generator, and writes Unity package metadata. It produces a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client.

The generic steps live here; the caller supplies the spec-production strategy (any callable from project directory to raw spec JSON — the org's uv convention ships as `dump_openapi_spec`), the project→client mapping, the naming root, the npm scope, license, repository URL, and the output root. See [`AGENTS.md`](./AGENTS.md) for the API surface, the lib-owns/consumer-owns boundary, and the patch mechanism.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- **Java (JDK 11+)** and **`uvx`** on PATH at runtime — the generator runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`

## CLI

A thin CLI exposes the OpenAPI 3.1→3.0 downgrade, single-client generation, and the multi-project orchestrator:

```bash
uv run openapi-client-codegen downgrade path/to/openapi.json            # 3.1→3.0 in place
uv run openapi-client-codegen downgrade path/to/openapi.json out.json   # write elsewhere

uv run openapi-client-codegen generate path/to/openapi.json generated/csharp/api-client \
  --root-name myproject --project services/api \
  --npm-scope org.example.myproject --license-spdx Apache-2.0 \
  --repository-url https://github.com/org/repo.git

uv run openapi-client-codegen generate-projects clients.json \
  --spec-command 'uv run --project . python -m src.dump_openapi' \
  --root-name myproject --generated-root generated \
  --npm-scope org.example.myproject --license-spdx Apache-2.0 \
  --repository-url https://github.com/org/repo.git
```

`clients.json` maps each project path to its client generators (`{"services/api": ["python", "csharp"]}`). `--spec-command` names the strategy: a shell command that prints the project's raw OpenAPI JSON to stdout, run with the project directory as cwd (env prefixes like `CODEGEN=1 …` inline directly). The orchestrator downgrades each produced spec, skips generation when the committed `<project>/openapi.json` is byte-identical (`--no-cache` forces through), and syncs each client under `<generated-root>/<generator>/<base-name>`.

The same surface is the library API, for in-process consumption from a consumer's own command — `dump_spec` is required, so every consumer names its strategy explicitly:

```python
import json
from pathlib import Path

from openapi_client_codegen.orchestrator import dump_openapi_spec, generate_projects

projects = json.loads(Path("clients.json").read_text(encoding="utf-8"))
generate_projects(
    projects,
    root_name="myproject",
    generated_root=Path("generated"),
    dump_spec=dump_openapi_spec,
    npm_scope="org.example.myproject",
    license_spdx="Apache-2.0",
    repository_url="https://github.com/org/repo.git",
)
```

A non-uv project passes its own callable instead — e.g. `dump_spec=lambda project: bash_output("dotnet run -- dump-openapi", cwd=project)`, or a file read for a project whose spec is committed rather than dumped.

## Consuming from another repo

Install from PyPI:

```toml
[project]
dependencies = ["openapi-client-codegen>=0.1.0"]
```

`bashrun` resolves transitively. At **runtime** the generator also needs Java (JDK 11+) and `uvx` on PATH. To test an unreleased change, pin the repo at a git ref in a scratch branch instead (`openapi-client-codegen = { git = "…", rev = "<sha>" }` under `[tool.uv.sources]`) and drop the pin when the release lands.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pytest
```
