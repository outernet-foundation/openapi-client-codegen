# Execution plan: typescript-fetch generator

Input: [typescript-fetch-generator.md](./typescript-fetch-generator.md) — fully ruled
(D1–D7). Scope: D3 — this repo only. The change is additive (new optional config field, new
param, new shipped config) → patch-auto under the existing `major_minor: "0.3"`; bump
manually only if the public API somehow breaks.

Ordered steps for the emitter session:

1. **Verify generator options** against the pin, not against doc prose:

   ```
   uvx --from 'openapi-generator-cli[jdk4py]==7.22.0' openapi-generator-cli config-help -g typescript-fetch
   ```

   Confirm the option names this plan assumes: `npmName`, `npmVersion`,
   `hideGenerationTimestamp`, and that the tests/docs `globalProperties` behave as in
   python.json. A real emission needs Java; unit tests never do (mocked `uvx`).

2. **Shipped config** — `_data/configs/typescript-fetch.json`, mirroring python.json:
   `generatorName`, globalProperties off for tests/docs, `hideGenerationTimestamp: true`,
   static `npmVersion: "0.1.0"` (versioning happens at publish time via the toolkit's
   manifest patch). No static `npmName` — it is per-consumer (D7).

3. **Config schema** — `orchestrator.py` `ProjectsConfig`: new optional
   `typescript_npm_scope: str | None` alongside `npm_scope` (which stays UPM/csharp-only).
   Value is the bare scope (`placeframe`, no `@`).

4. **CLI pass-through** — `cli.py`'s `generate_client` call site gains
   `typescript_npm_scope=settings.typescript_npm_scope`.

5. **Naming branch** — `client.py` (the `csharp`/`else` fork around line 39): add a
   `typescript-fetch` branch setting `additionalProperties["npmName"]` to
   `@{typescript_npm_scope}/{names.base}` when the scope is set, else `names.dashed` (D7
   fallback). No `templates_dir` requirement, no post-generation step (skip python's
   `uv pip install` and csharp's metadata write).

6. **Emit once for real** against a scratch spec — a hand-written minimal OpenAPI 3.0 doc
   under `/tmp/opencode` (D3 forbids touching placeframe). Inspect the emitted tree.

7. **Ignore file** — `_data/openapi-generator-ignore`: add global-basename entries for the
   generator's repo/CI baggage found in step 6 (`.travis.yml`/`.gitlab-ci.yml`/`.gitignore`
   are already covered; typescript-fetch may add its own). Curate against the actual tree
   only — no guessed filenames.

8. **Tests** — `tests/test_orchestrate.py`: extend `Recorder.fake_generate_client`'s
   signature with the new kwarg; add a typescript-fetch orchestration test (generator key,
   output dir `generated/typescript-fetch/api-client`); add a client-level composition
   test that mocks `bash` in `client`, reads the temp config the built command references,
   and asserts the composed `npmName` for scope-set and scope-unset cases.

9. **Docs (spec-first)** — root `AGENTS.md` "What this is" gains the third target
   (typescript-fetch, zero runtime deps, browser consumer); the `generate_client` entry
   documents the new param and the `npmName` composition; the `ProjectsConfig` optional
   list gains `typescript_npm_scope`; README's one-liner likewise. Prose commit separate
   from code, per repo convention.

Adoption (placeframe-side, later — sequenced in the ADR, not executed on this branch):
release 0.3.x, port PRs merge, npm org created, `requires` bump, `typescript-fetch` under
`workloads/api` with `typescript_npm_scope: placeframe`, regenerate, `publish.yml` entry
for `@placeframe/api-client`.
