# ADR: typescript-fetch as the third generated client target

Status: **Ruled** — D1–D7 decided (Tyler; D6–D7 in the follow-up session, same day).
Execution plan: [typescript-fetch-generator-plan.md](./typescript-fetch-generator-plan.md);
the next session executes it.

## Context

Placeframe's dashboard is being reworked from Howard's dev_hh prototype into a hosted SPA —
Vite + React + TypeScript + three.js, v1 unauthenticated, talking **directly** to the
placeframe API with no backend of its own. The dev_hh disposition record (report.md on the
frozen `dev_hh-refactor` branch, placeframe repo) lists a "TS api-client target in
openapi-client-codegen, published or tarball-referenced for npm consumption" as the item
that **gates all frontend migration** — every dashboard route that flips from Howard's
subprocess backend to a direct API call needs this client first.

This tool today emits two targets: a Python (`httpx`) client and a Unity-consumable C#
(`httpclient`) client. This ADR adds the third. The consumer is browser-only; Howard's
frontend currently has zero HTTP library dependencies.

## Decisions

- **D1 — Generator: `typescript-fetch`** (in the pinned openapi-generator-cli 7.22.0).
  Why: the consumer is a browser SPA; native `fetch` means the generated client has **zero
  runtime dependencies**. The axios-based `typescript` generator is labeled *experimental*
  in 7.22.0's own `list` output; `typescript-axios`, `typescript-node`, `typescript-rxjs`,
  and the rest are deprecated or non-browser. Consequence: consumers need an environment
  with `fetch` (every modern browser, Node ≥ 18, Deno) — acceptable for this consumer.
- **D2 — Authorship: Tyler** (via agent sessions). This supersedes the dev_hh port plan's
  next-batch note assigning the TS emitter to Howard as his first delegated code work /
  curriculum arc; that arc moves elsewhere. Recorded here so the supersession is visible
  where the work lands.
- **D3 — Scope: tool only.** This branch changes openapi-client-codegen and nothing else.
  All placeframe-side adoption work (see "Adoption sequencing") is a separate later effort.
- **D4 — Consumer-side coverage intent: `workloads/api` only.** The dashboard talks only to
  the api; the localizer and lease-server stay python-only. (Recorded for the adoption
  effort; nothing in the tool enforces or needs this.)
- **D5 — Branch name `typescript-generator`** (this branch).
- **D6 — Distribution: publish to public npm**, from placeframe's `publish.yml` via the
  existing NpmRegistry machinery (dev dist-tag channel included). Both the npm org
  `placeframe` and the unscoped name `placeframe-api-client` were unclaimed on npmjs.com
  as of 2026-11-18; creating the org is a foundation-side prerequisite, before the first
  publish.
- **D7 — npm identity: scoped and tool-composed.** The emitted name is
  `@placeframe/api-client`. The tool composes `npmName` as `@{typescript_npm_scope}/{base}`
  from a new optional `ProjectsConfig` field, falling back to unscoped `{dashed}` when
  unset — not a verbatim free-text name, and not the UPM reverse-domain identities (those
  serve Unity, not browsers).

## Mechanism sketch (input for the plan)

The existing orchestration loop is generator-agnostic — spec production, the 3.1→3.0
downgrade, the single-Default-tag forcing, the unchanged-spec skip, and the `--check`
staleness gate all derive from config and need no change. The emitter session touches:

- **`_data/configs/typescript-fetch.json`** — new, mirroring python.json/csharp.json:
  `generatorName`, globalProperties off for tests/docs, `hideGenerationTimestamp`, a static
  `npmVersion: "0.1.0"` (established pattern — real versioning happens at publish time, see
  "Version stamping" below), and `npmName` — composed per consumer by the naming branch
  (D7), never static in this file. Verify
  exact option names/defaults with `config-help -g typescript-fetch` at the pinned version;
  do not trust this doc's option names over config-help.
- **`client.generate_client` naming branch** — the current non-csharp `else` writes
  Python's `projectName`/`packageName`; typescript-fetch keys its package identity off
  npm-style options (`npmName`/`npmVersion` — verify). No `templates_dir` requirement (no
  template patches initially; patch only if stock output proves deficient, under the same
  path-generic patch convention as csharp). No post-generation step (python gets
  pip-installed into the venv; csharp gets Unity metadata written; the TS tree is just
  committed by the consumer).
- **Output location** — the CLI writes `generated_root / <generator-as-keyed> / <base>`,
  so placeframe will see `packages/generated/typescript-fetch/api-client/`.
- **`_data/openapi-generator-ignore` additions** for the generator's repo baggage
  (precedent: python's CI baggage got global-basename entries). Curate against the actual
  emitted tree in the emitter session; do not guess the file list here.
- **Tests** — extend the mocked-generator unit tests (tests/test_orchestrate.py's recorder
  pattern) for the naming branch and config load; no Java or Node needed in unit tests,
  per the existing pattern of mocking the `uvx` invocation.
- **Doc updates (spec-first, in the emitter session)** — root `AGENTS.md` "What this is"
  and the `generate_client` public-API entry gain the third target; README's one-liner
  likewise.
- **Release** — additive change → patch-auto under the existing `major_minor: "0.3"` line.
  If the emitter session discovers it must break the public API, bump `major_minor`
  manually per repo convention instead.

## Technical facts the plan should not re-derive

- Pin is openapi-generator-cli **7.22.0** (`resources.py`); `typescript` and
  `typescript-fetch` both exist in it (verified via `list`).
- Spec-level workarounds upstream of any generator already cover TS: the 3.1→3.0 downgrade,
  and the placeframe-side discipline of `list[list[float]]` over tuples (openapi-generator
  rejects `prefixItems` and exits 0 — this bit Howard once; it applies to TS equally).
- `format: int64` maps to `number` in TS; JS numbers are float64, so the multi-GiB
  magnitudes that broke the C# Int32 parse are not a TS hazard. The dev_hh port plan's rule
  "bigint-int64 must land on dev before any TS client generation" is spec-consistency
  sequencing, not a TS type problem.
- **Version stamping precedent**: generated trees carry a static package version; at
  publish time github-actions-toolkit's registry support rewrites the version (and
  intra-org dependency pins) via an ephemeral manifest patch, and treats EPUBLISHCONFLICT
  as an idempotent skip. Its NpmRegistry publishes with `npm publish --access public
  --provenance` and a dev dist-tag channel. Placeframe already publishes the C# api-client
  to both nuget and npm this way (`publish.yml`: `PlaceframeApiClient` /
  `org.outernet.placeframe.apiclient`). A published TS client would ride this machinery.
- **npm identity is baked at generation time**: typescript-fetch writes `npmName` into the
  generated `package.json`, and the publish tooling patches only the version — so even an
  unpublished TS tree needs a package name, and renaming it later churns the committed tree
  through the staleness gate. This is why the identity ruling (D7) could not be deferred.
- v1 auth posture: the dashboard is unauthenticated (placeframe `auth_mode = "disabled"`),
  so the emitted client carries **no auth plumbing** — a conscious default, not an
  oversight; typescript-fetch middleware can add auth when the deferred user-facing auth
  work lands.

## Adoption sequencing (placeframe-side, later; not this branch)

1. This tool releases 0.3.x to PyPI.
2. The five dev_hh port PRs merge — at minimum the bigint-int64 one — so placeframe's spec
   is final (as of 2026-11-18 none of the five PRs were open yet).
3. The foundation creates the `placeframe` npm org (D6).
4. Placeframe bumps `openapi-client-codegen.yaml` `requires` to `>=0.3`, adds
   `typescript-fetch` under `workloads/api` with `typescript_npm_scope: placeframe`,
   regenerates (canonical `Run generate-clients`
   commit), and adds a `publish.yml` entry publishing `@placeframe/api-client` (D6/D7).
