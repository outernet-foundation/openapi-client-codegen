# openapi-client-codegen

## What this is

`openapi-client-codegen` wraps [OpenAPI Generator](https://openapi-generator.tech/) to turn an OpenAPI schema into typed client packages — a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client. It owns every step that is generic across consumers: the project orchestration loop, downgrading 3.1→3.0, the committed-spec unchanged skip, authoring and patching the C# templates, running the generator, and writing the Unity package metadata. The caller owns what is inherently project-specific: **producing the OpenAPI spec** (injected as a required strategy — any callable from project directory to raw spec JSON; the org's uv convention ships as `dump_openapi_spec`), the project→client mapping, the naming root, the npm scope, license, repository URL, and the generated output root.

The package is `openapi_client_codegen` (src-layout under `src/openapi_client_codegen/`), renamed from `openapi-clientgen` before the first publish (operator, 2026-09-20 — no artifact carries the old name). Its Python dependencies are `bashrun` (the guardrailed subprocess wrapper) and `typer` (the thin CLI), both from PyPI — git-source pins only in scratch branches testing unreleased changes. At **runtime** it also needs **Java (JDK 11+)** and **`uvx`** on PATH — the generator itself runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`.

## Release flow

Publishing rides `ci.yml`'s `publish` job on every push to `main` (gated on the check job): release-devkit's publish composite action (pinned by SHA; the uvx invocation runs inside the caller's job, keeping OIDC identity local), never a project dependency (openapi-client-codegen sits inside release-devkit's transitive dependency graph; a project-level edge is a resolver cycle) — computes the plan from the tag ledger and path-diff, patches the version ephemerally, and publishes to PyPI under OIDC trusted publishing (pending publisher bound to `ci.yml`, no environment). The committed `pyproject.toml` version is permanently the `0.0.0.dev0` sentinel; the `openapi-client-codegen-v*` tags are the version ledger (first release `0.1.0`, patch-auto thereafter). API-breaking changes ship with a manually bumped version — patch-auto assumes additive changes.

## Public API

The package init is empty (RUF067 strict mode — the canonical ruff config bans any content in `__init__.py`); import each symbol from its defining module: `client` (`generate_client`), `downgrade` (`downgrade_openapi_3_1_to_3_0`, `JsonDict`), `naming` (`ClientNaming`, `DefaultNamingPolicy`, `NamingPolicy`), `orchestrator` (`generate_projects`, `dump_openapi_spec`, `SpecProducer`), `templates` (`regenerate_templates`), `unity` (`write_unity_package_metadata`).

| Symbol | Role |
|---|---|
| `downgrade_openapi_3_1_to_3_0(schema)` | In-place 3.1.0→3.0.3 fixup (openapi-generator rejects 3.1). Pure function. |
| `generate_projects(projects, root_name, generated_root, dump_spec, npm_scope=None, license_spdx=None, repository_url=None, project=None, client=None, no_cache=False, root=Path())` | The project orchestrator: per mapping entry (`{project path: [generators]}`), produce the spec via the injected `dump_spec` strategy, downgrade it, write `<project>/openapi.json` unless byte-identical to the committed spec (`no_cache` forces through), and `generate_client` per listed generator into `<generated_root>/<generator>/<names.base>`. `project` / `client` restrict the run to one entry; `root` is what project paths resolve against. |
| `SpecProducer(command)` | Callable class wrapping any shell command that prints the spec to stdout, run with the project directory as cwd; the CLI `--spec-command` bridge. The strategy contract itself is untyped vocabulary — any `Callable[[Path], str]` (project directory in, raw OpenAPI JSON out) satisfies `dump_spec`. |
| `dump_openapi_spec(project)` | The org strategy: `uv run --project . python -m src.dump_openapi` with `CODEGEN=1` gating heavy imports (per-call env overlay). Shipped as the exemplar — `dump_spec` is required, so every consumer names its strategy explicitly. |
| `regenerate_templates(target_dir, extra_patches_dir=None)` | Author the C# templates into `target_dir/csharp` and apply the shipped (then optional extra) patches. |
| `generate_client(spec, generator, output_dir, names, templates_dir=None, extra_references=None, npm_scope=None, license_spdx=None, repository_url=None)` | Run the generator for one `(spec, generator)` and sync the result into `output_dir`. `templates_dir` is required for `csharp`. For csharp, `npm_scope` composes the UPM identity `{scope}.{base-minus-dashes}` (e.g. `org.outernet.placeframe.apiclient`); unset falls back to the legacy `org.nuget.{camel-lower}` identity. `license_spdx` / `repository_url` populate the manifest's `license` / `repository` fields when given. |
| `write_unity_package_metadata(package_dir, package_name, extra_references=None, npm_name=None, license_spdx=None, repository_url=None)` | Write `package.json` / `.asmdef` / `csc.rsp` / `Directory.Build.props`. Called by `generate_client` for csharp. |
| `DefaultNamingPolicy(root_name)` / `ClientNaming` / `NamingPolicy` | Package-name derivation. `DefaultNamingPolicy("placeframe")("docker/api")` → base `api-client`, dashed `placeframe-api-client`, underscored `placeframe_api_client`, camel `PlaceframeApiClient`. |

`generate_projects` orchestrates the whole run — `regenerate_templates` once, then per project: produce (via the injected strategy) → downgrade → committed-spec skip → per-client generate. Consumers hand it their parsed mapping, their spec-production strategy, and their identity parameters. The generator version pin and the shipped configs/patches/ignore-file live in `src/openapi_client_codegen/_data/` (paths in `_data.py`).

## Constraints

### The C# template patches are path-generic and repo-independent

The shipped patches (`_data/templates-patches/csharp/00NN-*.patch`) carry generic `a/csharp/<path>` headers, not any consumer's repo layout. `regenerate_templates` applies them with `git apply -p1` and `cwd=target_dir`, which lands them on the freshly-authored tree **without needing a surrounding git repository** — `git apply` patches worktree files fine outside any repo as long as `--index` is not used. Patches apply in filename order (the `00NN` prefix is load-bearing: later patches depend on earlier hunks' context); `extra_patches_dir` patches apply after the shipped set.

To author a new patch: author the raw templates (`openapi-generator-cli author template -g csharp --library httpclient`) into a scratch dir, copy it, edit a `.mustache` in the copy, `git diff --no-index` the two trees, and normalize the diff's path headers to `csharp/<path>` so it applies under the same `-p1` convention.

### Generator env vars are passed per-call, never set at module level

`JAVA_OPTS=-Dlog.level=warn` (quiets the generator) is passed as `bash(..., env={"JAVA_OPTS": "-Dlog.level=warn"})` on the two `openapi-generator-cli` calls that need it, so it reaches only those child processes and never touches this process's `os.environ`. `bashrun`'s `env=` overlays the inherited environment for that one child (see its AGENTS.md), which is the whole point — the alternative, mutating the global `os.environ`, leaks the var into every later subprocess. This covers only the generator this package runs itself. The shipped `dump_openapi_spec` strategy follows the same rule: `CODEGEN=1` (which gates a service's heavy imports so the app imports cleanly for the dump) rides bashrun's per-call env overlay and never touches this process's `os.environ`.

### The Unity reference set is coupled to the patched templates

`unity.write_unity_package_metadata` hardcodes the `.asmdef` base references `Newtonsoft.Json / Polly / JsonSubTypes`. These are exactly the runtime support the patched C# templates emit calls against (Polly retry, JsonSubTypes discriminators, Newtonsoft serialization). They travel with the patches as one unit; a consumer adds project-specific references via `extra_references`, it does not replace the base set.

`BASE_DEPENDENCIES` is the UPM dual of that reference set: the same three libraries expressed as `package.json` dependencies (Newtonsoft as the Unity-blessed `com.unity.nuget.newtonsoft-json`, the others as UnityNuGet `org.nuget.*` identities), as exact versions — UPM's package.json dependencies accept SemVer values only, no range syntax, and the resolver treats a value as a minimum, so consumer manifests carrying newer minors still resolve without conflict. It travels with `BASE_REFERENCES` — change one, change the other.

### The csproj ships in the package; MSBuild output is redirected around it

The generated `.csproj` stays inside the UPM package because it is the `dotnet pack` input for the nuget feed. To keep IDE builds from writing `bin/`/`obj/` into the package (Unity errors on the missing `.meta` files, and the npm tarball must not carry build output), `write_unity_package_metadata` writes a `Directory.Build.props` next to it that redirects `BaseIntermediateOutputPath` / `BaseOutputPath` two directories up — outside the package root under every consumption layout (repo checkout → client grouping dir; Unity PackageCache → `Library/`, which the asset importer ignores). The shipped template patch `0008` points the csproj's `DocumentationFile` at `$(BaseOutputPath)` for the same reason; `Directory.Build.props` is imported before the project body, so the property is visible at that evaluation point.

### What the consumer owns

The spec-production strategy (`dump_spec`, required — the package is consumable by projects that use no Python, no uv, or no dump entry point at all; the org's `dump_openapi_spec` ships beside it, and a project whose spec is a committed file needs only a file read), the project→clients mapping (in whatever config shape it likes — the verb takes the parsed mapping, not a file path), the naming root, the npm scope, license, repository URL, and the generated output root. The orchestrator iterates the mapping itself and fixes `DefaultNamingPolicy`; a consumer needing a different policy calls the per-client API directly — `NamingPolicy` is a `Protocol`, any callable `(project: str) -> ClientNaming` works there.

## See also

- `README.md` — human-facing setup and usage.
- [`bashrun`](https://github.com/outernet-foundation/bashrun) — the subprocess wrapper this package shells out through.
