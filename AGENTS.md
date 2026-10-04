# openapi-client-codegen

## What this is

`openapi-client-codegen` wraps [OpenAPI Generator](https://openapi-generator.tech/) to turn an OpenAPI schema into typed client packages — a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client. It owns every step that is generic across consumers: the project orchestration loop, downgrading 3.1→3.0, the committed-spec unchanged skip, authoring and patching the C# templates, running the generator, and writing the Unity package metadata. The caller owns what is inherently project-specific: **producing the OpenAPI spec** (a command string in the consumer's config, run by the library's `SpecProducer`), the project→client mapping, the naming root, the npm scope, license, repository URL, and the generated output root.

The package is `openapi_client_codegen` (src-layout under `src/openapi_client_codegen/`). Python dependencies: `bashrun`, `packaging` (`requires` specifier parsing), `pydantic` (config schema), `strictyaml` (config loading), `typer` (thin CLI) — all from PyPI; git-source pins only in scratch branches testing unreleased changes. At **runtime** it also needs **Java (JDK 11+)** and **`uvx`** on PATH — the generator itself runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`.

## Public API

The package init is empty (RUF067 strict mode); import each symbol from its defining module: `client` (`generate_client`), `cli` (`app`), `downgrade` (`downgrade_openapi_3_1_to_3_0`, `JsonDict`), `orchestrator` (`ProjectsConfig`, `ClientNaming`, `SpecProducer`, `load_config`), `templates` (`regenerate_templates`), `unity` (`write_unity_package_metadata`).

- `ProjectsConfig` is the pydantic schema of a consumer's config (`extra="forbid"`) and the single source of identity — the CLI validates `--config` into it and nothing overrides it per invocation. Required: `projects` (project path → generator list), `root_name`, `generated_root`, `spec_command`, `requires` (a PEP 440 specifier; `load_config` self-checks the installed version and refuses outside range; "no constraint" is explicit `requires: ">=0.0"`; the `0.0.0.dev0` dev sentinel bypasses the check, not the field's presence). Optional: `spec_env`, `npm_scope`, `license_spdx`, `repository_url`.
- The CLI (`app`, single command, no subcommand; consumer `[project.scripts]` aliases point at it, e.g. placeframe's `generate-clients`) orchestrates per mapping entry: produce the spec via the config-built `SpecProducer` → downgrade 3.1→3.0 → write `<project>/openapi.json` unless byte-identical to the committed spec (`--no-cache` forces through) → `generate_client` per listed generator into `<generated_root>/<generator>/<base>`. `--check` is the CI staleness gate: unconditional regen, non-zero exit if any spec or generated client differs from the committed tree; the checked paths are fully derived from config, no per-consumer path args. Flags are invocation-scoped only (`--project`/`--client` filters, `--no-cache`, `--check`, `--root`). Commands run shell-less (shlex-split, operators rejected) — env gating is the structured `spec_env`, never a `VAR=…` prefix.
- `SpecProducer(command, env=None)` — callable class wrapping any command that prints the spec to stdout, run with the project directory as cwd and an optional per-call env overlay; programmatic consumers construct it directly.
- `ClientNaming` — the derived per-project package identity: `base` (last path segment + `-client`), `dashed` (`{root_name}-{base}`), `underscored`, `camel`. Constructed inline by the CLI per project; a consumer needing different names calls the per-client API directly with its own `ClientNaming`.
- `generate_client(spec, generator, output_dir, names, ...)` — run the generator for one `(spec, generator)` and sync into `output_dir`; `templates_dir` is required for `csharp`, where `npm_scope` composes the UPM identity `{scope}.{base-minus-dashes}` (unset falls back to the legacy `org.nuget.{camel-lower}`).
- `write_unity_package_metadata(...)` — write `package.json` / `.asmdef` / `csc.rsp` / `Directory.Build.props`; called by `generate_client` for csharp.

The generator version pin and the shipped configs/patches/ignore-file live in `src/openapi_client_codegen/_data/` (paths in `_data.py`).

## Constraints

### The C# template patches are path-generic and repo-independent

The shipped patches (`_data/templates-patches/csharp/00NN-*.patch`) carry generic `a/csharp/<path>` headers, not any consumer's repo layout. `regenerate_templates` applies them with `git apply -p1` and `cwd=target_dir`, which lands them on the freshly-authored tree **without needing a surrounding git repository** — `git apply` patches worktree files fine outside any repo as long as `--index` is not used. Patches apply in filename order (the `00NN` prefix is load-bearing: later patches depend on earlier hunks' context); `extra_patches_dir` patches apply after the shipped set.

To author a new patch: author the raw templates (`openapi-generator-cli author template -g csharp --library httpclient`) into a scratch dir, copy it, edit a `.mustache` in the copy, `git diff --no-index` the two trees, and normalize the diff's path headers to `csharp/<path>` so it applies under the same `-p1` convention.

### Generator env vars are passed per-call, never set at module level

`JAVA_OPTS=-Dlog.level=warn` (quiets the generator) is passed as `bash(..., env={"JAVA_OPTS": "-Dlog.level=warn"})` on the two `openapi-generator-cli` calls that need it — bashrun's `env=` overlays the inherited environment for that one child only. A consumer's spec command needing the same gating (e.g. `CODEGEN=1`) carries it in the config's structured `spec_env` key, which rides the same per-call overlay.

### The Unity reference set is coupled to the patched templates

`unity.write_unity_package_metadata` hardcodes the `.asmdef` base references `Newtonsoft.Json / Polly / JsonSubTypes` — exactly the runtime support the patched C# templates emit calls against. They travel with the patches as one unit; a consumer adds project-specific references via `extra_references`, it does not replace the base set.

`BASE_DEPENDENCIES` is the UPM dual of that reference set: the same three libraries as `package.json` dependencies (Newtonsoft as the Unity-blessed `com.unity.nuget.newtonsoft-json`, the others as UnityNuGet `org.nuget.*` identities), as exact versions — UPM's package.json dependencies accept SemVer values only, and the resolver treats a value as a minimum, so consumer manifests carrying newer minors still resolve. It travels with `BASE_REFERENCES` — change one, change the other.

### The csproj ships in the package; MSBuild output is redirected around it

The generated `.csproj` stays inside the UPM package because it is the `dotnet pack` input for the nuget feed. To keep IDE builds from writing `bin/`/`obj/` into the package (Unity errors on the missing `.meta` files, and the npm tarball must not carry build output), `write_unity_package_metadata` writes a `Directory.Build.props` next to it that redirects `BaseIntermediateOutputPath` / `BaseOutputPath` two directories up — outside the package root under every consumption layout (repo checkout → client grouping dir; Unity PackageCache → `Library/`, which the asset importer ignores). The shipped template patch `0008` points the csproj's `DocumentationFile` at `$(BaseOutputPath)` for the same reason; `Directory.Build.props` is imported before the project body, so the property is visible at that evaluation point.

## Release flow

release-devkit's `AGENTS.md` owns the three-workflow contract; this repo follows it unchanged. Repo-specific facts: release-devkit is never a project dependency (this package sits inside release-devkit's transitive dependency graph; a project-level edge is a resolver cycle), and API-breaking changes ship with a manually bumped `major_minor` (patch-auto assumes additive changes).

## See also

- [`bashrun`](https://github.com/outernet-foundation/bashrun) — the subprocess wrapper this package shells out through.
