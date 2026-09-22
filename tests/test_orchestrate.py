import copy
import json
from pathlib import Path

import pytest

from openapi_client_codegen import (
    ClientNaming,
    CommandSpecProducer,
    SpecProducer,
    downgrade_openapi_3_1_to_3_0,
    dump_openapi_spec,
    generate_projects,
)
from openapi_client_codegen import orchestrator
from openapi_client_codegen.downgrade import JsonDict

RAW_SCHEMA: JsonDict = {"openapi": "3.1.0", "info": {"title": "demo", "version": "0.0.0"}, "paths": {}}


class Recorder:
    def __init__(self) -> None:
        self.generated: list[tuple[str, Path, ClientNaming]] = []
        self.dumps: list[Path | None] = []
        self.commands: list[tuple[str, Path | None, dict[str, str] | None]] = []

    def fake_dump_spec(self, project: Path) -> str:
        self.dumps.append(project)
        return json.dumps(RAW_SCHEMA)

    def fake_bash_output(self, command: str, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
        self.commands.append((command, cwd, env))
        return json.dumps(RAW_SCHEMA)

    def fake_regenerate_templates(self, target_dir: Path, extra_patches_dir: Path | None = None) -> None:
        pass

    def fake_generate_client(
        self,
        spec: str,
        generator: str,
        output_dir: Path,
        names: ClientNaming,
        templates_dir: Path | None = None,
        extra_references: list[str] | None = None,
        npm_scope: str | None = None,
        license_spdx: str | None = None,
        repository_url: str | None = None,
    ) -> None:
        self.generated.append((generator, output_dir, names))


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(orchestrator, "bash_output", recorder.fake_bash_output)
    monkeypatch.setattr(orchestrator, "regenerate_templates", recorder.fake_regenerate_templates)
    monkeypatch.setattr(orchestrator, "generate_client", recorder.fake_generate_client)
    return recorder


def downgraded_spec() -> str:
    schema = copy.deepcopy(RAW_SCHEMA)
    downgrade_openapi_3_1_to_3_0(schema)
    return json.dumps(schema, indent=2)


def make_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    return project


def test_generates_all_clients_and_writes_downgraded_spec(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/api")

    generate_projects(
        {"docker/api": ["python", "csharp"]},
        "placeframe",
        tmp_path / "generated",
        recorder.fake_dump_spec,
        root=tmp_path,
    )

    assert [(generator, output_dir.name) for generator, output_dir, _ in recorder.generated] == [
        ("python", "api-client"),
        ("csharp", "api-client"),
    ]
    assert all(output_dir.parent.parent == tmp_path / "generated" for _, output_dir, _ in recorder.generated)

    written = (tmp_path / "docker" / "api" / "openapi.json").read_text(encoding="utf-8")
    assert written == downgraded_spec()
    assert json.loads(written)["openapi"] == "3.0.3"

    assert recorder.dumps == [tmp_path.resolve() / "docker" / "api"]


def test_skips_generation_when_committed_spec_unchanged(tmp_path: Path, recorder: Recorder) -> None:
    project = make_project(tmp_path, "docker/api")
    (project / "openapi.json").write_text(downgraded_spec(), encoding="utf-8")

    generate_projects(
        {"docker/api": ["python"]}, "placeframe", tmp_path / "generated", recorder.fake_dump_spec, root=tmp_path
    )

    assert recorder.generated == []


def test_no_cache_forces_generation_despite_unchanged_spec(tmp_path: Path, recorder: Recorder) -> None:
    project = make_project(tmp_path, "docker/api")
    (project / "openapi.json").write_text(downgraded_spec(), encoding="utf-8")

    generate_projects(
        {"docker/api": ["python"]},
        "placeframe",
        tmp_path / "generated",
        recorder.fake_dump_spec,
        no_cache=True,
        root=tmp_path,
    )

    assert len(recorder.generated) == 1


def test_project_and_client_filters(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/api")
    make_project(tmp_path, "docker/localizer")

    generate_projects(
        {"docker/api": ["python", "csharp"], "docker/localizer": ["python"]},
        "placeframe",
        tmp_path / "generated",
        recorder.fake_dump_spec,
        project="docker/api",
        client="csharp",
        root=tmp_path,
    )

    assert len(recorder.generated) == 1
    generator, output_dir, names = recorder.generated[0]
    assert generator == "csharp"
    assert output_dir == tmp_path / "generated" / "csharp" / "api-client"
    assert names.dashed == "placeframe-api-client"


def test_dump_openapi_spec_pins_the_org_convention(recorder: Recorder) -> None:
    dump_openapi_spec(Path("docker/api"))

    assert len(recorder.commands) == 1
    command, cwd, env = recorder.commands[0]
    assert command == "uv run --project . python -m src.dump_openapi"
    assert cwd == Path("docker/api")
    assert env == {"CODEGEN": "1"}


def test_command_spec_producer_runs_with_project_cwd(recorder: Recorder) -> None:
    producer: SpecProducer = CommandSpecProducer("dotnet run -- dump-openapi")

    produced = producer(Path("services/api"))

    assert json.loads(produced) == RAW_SCHEMA
    assert recorder.commands == [("dotnet run -- dump-openapi", Path("services/api"), None)]
