# openapi-client-codegen

Generate typed API clients from an OpenAPI schema. `openapi-client-codegen` wraps [OpenAPI Generator](https://openapi-generator.tech/): it downgrades OpenAPI 3.1→3.0 (the generator only accepts 3.0), authors and patches the C# templates, runs the generator, and writes Unity package metadata. It produces a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client.

The generic steps live here; the caller supplies the spec-production strategy (any callable from project directory to raw spec JSON — a shell command carried in the CLI config), the project→client mapping, the naming root, the npm scope, license, repository URL, and the output root. See [`AGENTS.md`](./AGENTS.md) for the API surface, the lib-owns/consumer-owns boundary, and the patch mechanism.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- **Java (JDK 11+)** and **`uvx`** on PATH at runtime — the generator runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`

## CLI

The CLI is the multi-project orchestrator, invoked directly (single command, no subcommand):

```bash
uv run openapi-client-codegen --config clients.json
```

`clients.json` carries everything consumer-owned in one place:

```json
{
  "projects": {"services/api": ["python", "csharp"]},
  "root_name": "myproject",
  "generated_root": "generated",
  "spec_command": "uv run --project . python -m src.dump_openapi",
  "spec_env": {"CODEGEN": "1"},
  "npm_scope": "org.example.myproject",
  "license_spdx": "Apache-2.0",
  "repository_url": "https://github.com/org/repo.git"
}
```

`spec_command` is a command that prints the project's raw OpenAPI JSON to stdout, run with the project directory as cwd — no shell sits in front of it (commands are shlex-split; operators like `|` are rejected), so env gating rides the structured `spec_env` key, overlaid per call. The config is the single source of identity: `root_name`, `generated_root`, and `spec_command` are required there, and nothing overrides them per invocation — a different identity is a different config file. The remaining flags are invocation-scoped (`--project` / `--client` filters, `--no-cache`, `--root`). The orchestrator downgrades each produced spec, skips generation when the committed `<project>/openapi.json` is byte-identical (`--no-cache` forces through), and syncs each client under `<generated-root>/<generator>/<base-name>`.

To run it as a first-class command in a consumer repo, point a `[project.scripts]` entry at the same app — e.g. `generate-clients = "openapi_client_codegen.cli:app"`.

The same config drives the library API, for in-process consumption from a consumer's own command:

```python
from pathlib import Path

from openapi_client_codegen.orchestrator import ProjectsConfig, generate_projects

config = ProjectsConfig.model_validate_json(Path("clients.json").read_text(encoding="utf-8"))
generate_projects(config)
```

A non-uv project declares its own `spec_command` instead — e.g. `dotnet run -- dump-openapi`; a project whose spec is a committed file uses `cat openapi.json`.

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
