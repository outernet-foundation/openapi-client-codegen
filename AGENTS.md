# openapi-clientgen

## What this is

`openapi-clientgen` wraps [OpenAPI Generator](https://openapi-generator.tech/) to turn an OpenAPI schema into typed client packages — a Python (`httpx`) client and a Unity-consumable C# (`httpclient`) client. It owns every step that is generic across consumers: downgrading 3.1→3.0, authoring and patching the C# templates, running the generator, and writing the Unity package metadata. The caller owns what is inherently project-specific: **producing the OpenAPI spec** (however its app exposes one), which projects map to which clients, the package-name policy, and the output paths.

The package is `openapi_clientgen` (src-layout under `src/openapi_clientgen/`). Its Python dependencies are `bashrun` (the guardrailed subprocess wrapper) and `typer` (the thin CLI). At **runtime** it also needs **Java (JDK 11+)** and **`uvx`** on PATH — the generator itself runs as `uvx --from 'openapi-generator-cli[jdk4py]==<pin>' ...`.

## Public API

`__init__` re-exports the surface; import from the package root.

| Symbol | Role |
|---|---|
| `downgrade_openapi_3_1_to_3_0(schema)` | In-place 3.1.0→3.0.3 fixup (openapi-generator rejects 3.1). Pure function. |
| `regenerate_templates(target_dir, extra_patches_dir=None)` | Author the C# templates into `target_dir/csharp` and apply the shipped (then optional extra) patches. |
| `generate_client(spec, generator, output_dir, names, templates_dir=None, extra_references=None, npm_scope=None, license_spdx=None, repository_url=None)` | Run the generator for one `(spec, generator)` and sync the result into `output_dir`. `templates_dir` is required for `csharp`. For csharp, `npm_scope` composes the UPM identity `{scope}.{base-minus-dashes}` (e.g. `org.outernet.placeframe.apiclient`); unset falls back to the legacy `org.nuget.{camel-lower}` identity. `license_spdx` / `repository_url` populate the manifest's `license` / `repository` fields when given. |
| `write_unity_package_metadata(package_dir, package_name, extra_references=None, npm_name=None, license_spdx=None, repository_url=None)` | Write `package.json` / `.asmdef` / `csc.rsp` / `Directory.Build.props`. Called by `generate_client` for csharp. |
| `DefaultNamingPolicy(root_name)` / `ClientNaming` / `NamingPolicy` | Package-name derivation. `DefaultNamingPolicy("placeframe")("docker/api")` → base `api-client`, dashed `placeframe-api-client`, underscored `placeframe_api_client`, camel `PlaceframeApiClient`. |

A consumer orchestrates: `regenerate_templates(tmp)` once, then per `(project, client)` produce the spec, `downgrade` it, and call `generate_client`. The generator version pin and the shipped configs/patches/ignore-file live in `src/openapi_clientgen/_data/` (paths in `_data.py`).

## Constraints

### The C# template patches are path-generic and repo-independent

The shipped patches (`_data/templates-patches/csharp/00NN-*.patch`) carry generic `a/csharp/<path>` headers, not any consumer's repo layout. `regenerate_templates` applies them with `git apply -p1` and `cwd=target_dir`, which lands them on the freshly-authored tree **without needing a surrounding git repository** — `git apply` patches worktree files fine outside any repo as long as `--index` is not used. Patches apply in filename order (the `00NN` prefix is load-bearing: later patches depend on earlier hunks' context); `extra_patches_dir` patches apply after the shipped set.

To author a new patch: author the raw templates (`openapi-generator-cli author template -g csharp --library httpclient`) into a scratch dir, copy it, edit a `.mustache` in the copy, `git diff --no-index` the two trees, and normalize the diff's path headers to `csharp/<path>` so it applies under the same `-p1` convention.

### Generator env vars are passed per-call, never set at module level

`JAVA_OPTS=-Dlog.level=warn` (quiets the generator) is passed as `bash(..., env={"JAVA_OPTS": "-Dlog.level=warn"})` on the two `openapi-generator-cli` calls that need it, so it reaches only those child processes and never touches this process's `os.environ`. `bashrun`'s `env=` overlays the inherited environment for that one child (see its AGENTS.md), which is the whole point — the alternative, mutating the global `os.environ`, leaks the var into every later subprocess. This covers only the generator this package runs itself; a consumer's spec-production step owns its own environment (e.g. any import-gating flag its services read).

### The Unity reference set is coupled to the patched templates

`unity.write_unity_package_metadata` hardcodes the `.asmdef` base references `Newtonsoft.Json / Polly / JsonSubTypes`. These are exactly the runtime support the patched C# templates emit calls against (Polly retry, JsonSubTypes discriminators, Newtonsoft serialization). They travel with the patches as one unit; a consumer adds project-specific references via `extra_references`, it does not replace the base set.

`BASE_DEPENDENCIES` is the UPM dual of that reference set: the same three libraries expressed as `package.json` dependencies (Newtonsoft as the Unity-blessed `com.unity.nuget.newtonsoft-json`, the others as UnityNuGet `org.nuget.*` identities), as version ranges so consumer manifests carrying newer minors don't conflict. It travels with `BASE_REFERENCES` — change one, change the other.

### The csproj ships in the package; MSBuild output is redirected around it

The generated `.csproj` stays inside the UPM package because it is the `dotnet pack` input for the nuget feed. To keep IDE builds from writing `bin/`/`obj/` into the package (Unity errors on the missing `.meta` files, and the npm tarball must not carry build output), `write_unity_package_metadata` writes a `Directory.Build.props` next to it that redirects `BaseIntermediateOutputPath` / `BaseOutputPath` two directories up — outside the package root under every consumption layout (repo checkout → client grouping dir; Unity PackageCache → `Library/`, which the asset importer ignores). The shipped template patch `0008` points the csproj's `DocumentationFile` at `$(BaseOutputPath)` for the same reason; `Directory.Build.props` is imported before the project body, so the property is visible at that evaluation point.

### What the consumer owns

The project→clients mapping, the naming policy, and the output paths are the consumer's. This package ships `DefaultNamingPolicy` as a convenience but defines no schema for the mapping file — the consumer iterates its own config and calls the API per entry. `NamingPolicy` is a `Protocol`; a consumer can supply any callable `(project: str) -> ClientNaming`.

## See also

- `README.md` — human-facing setup and usage.
- [`bashrun`](https://github.com/outernet-foundation/bashrun) — the subprocess wrapper this package shells out through.
