import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openapi_client_codegen import cli, orchestrator
from openapi_client_codegen.cli import app
from openapi_client_codegen.downgrade import JsonDict, downgrade_openapi_3_1_to_3_0
from openapi_client_codegen.orchestrator import ClientNaming, SpecProducer

runner = CliRunner()

RAW_SCHEMA: JsonDict = {"openapi": "3.1.0", "info": {"title": "demo", "version": "0.0.0"}, "paths": {}}


class Recorder:
    def __init__(self) -> None:
        self.generated: list[tuple[str, Path, ClientNaming]] = []
        self.commands: list[tuple[str, Path | None, dict[str, str] | None]] = []

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
    monkeypatch.setattr(cli, "regenerate_templates", recorder.fake_regenerate_templates)
    monkeypatch.setattr(cli, "generate_client", recorder.fake_generate_client)
    return recorder


def downgraded_spec() -> str:
    schema = copy.deepcopy(RAW_SCHEMA)
    downgrade_openapi_3_1_to_3_0(schema)
    return json.dumps(schema, indent=2)


def invoke(tmp_path: Path, projects: dict[str, list[str]], *args: str) -> None:
    settings: dict[str, object] = {
        "projects": projects,
        "root_name": "placeframe",
        "generated_root": str(tmp_path / "generated"),
        "spec_command": "dump-openapi",
    }
    config = tmp_path / "clients.json"
    config.write_text(json.dumps(settings), encoding="utf-8")

    result = runner.invoke(app, ["--config", str(config), "--root", str(tmp_path), *args])
    assert result.exit_code == 0


def make_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir(parents=True)
    return project


def test_generates_all_clients_and_writes_downgraded_spec(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/api")

    invoke(tmp_path, {"docker/api": ["python", "csharp"]})

    assert [(generator, output_dir.name) for generator, output_dir, _ in recorder.generated] == [
        ("python", "api-client"),
        ("csharp", "api-client"),
    ]
    assert all(output_dir.parent.parent == tmp_path / "generated" for _, output_dir, _ in recorder.generated)

    written = (tmp_path / "docker" / "api" / "openapi.json").read_text(encoding="utf-8")
    assert written == downgraded_spec()
    assert json.loads(written)["openapi"] == "3.0.3"

    assert recorder.commands == [("dump-openapi", tmp_path.resolve() / "docker" / "api", None)]


def test_skips_generation_when_committed_spec_unchanged(tmp_path: Path, recorder: Recorder) -> None:
    project = make_project(tmp_path, "docker/api")
    (project / "openapi.json").write_text(downgraded_spec(), encoding="utf-8")

    invoke(tmp_path, {"docker/api": ["python"]})

    assert recorder.generated == []


def test_no_cache_forces_generation_despite_unchanged_spec(tmp_path: Path, recorder: Recorder) -> None:
    project = make_project(tmp_path, "docker/api")
    (project / "openapi.json").write_text(downgraded_spec(), encoding="utf-8")

    invoke(tmp_path, {"docker/api": ["python"]}, "--no-cache")

    assert len(recorder.generated) == 1


def test_project_and_client_filters(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/api")
    make_project(tmp_path, "docker/localizer")

    invoke(
        tmp_path,
        {"docker/api": ["python", "csharp"], "docker/localizer": ["python"]},
        "--project",
        "docker/api",
        "--client",
        "csharp",
    )

    assert len(recorder.generated) == 1
    generator, output_dir, names = recorder.generated[0]
    assert generator == "csharp"
    assert output_dir == tmp_path / "generated" / "csharp" / "api-client"
    assert names.dashed == "placeframe-api-client"


def test_spec_env_rides_the_spec_command(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/api")

    settings: dict[str, object] = {
        "projects": {"docker/api": ["python"]},
        "root_name": "placeframe",
        "generated_root": str(tmp_path / "generated"),
        "spec_command": "dump-openapi",
        "spec_env": {"CODEGEN": "1"},
    }
    config = tmp_path / "clients.json"
    config.write_text(json.dumps(settings), encoding="utf-8")
    result = runner.invoke(app, ["--config", str(config), "--root", str(tmp_path)])
    assert result.exit_code == 0

    assert recorder.commands == [("dump-openapi", tmp_path.resolve() / "docker" / "api", {"CODEGEN": "1"})]


def test_naming_derives_from_root_and_last_segment(tmp_path: Path, recorder: Recorder) -> None:
    make_project(tmp_path, "docker/lease-server")

    invoke(tmp_path, {"docker/lease-server": ["python"]})

    names = recorder.generated[0][2]
    assert names.base == "lease-server-client"
    assert names.dashed == "placeframe-lease-server-client"
    assert names.underscored == "placeframe_lease_server_client"
    assert names.camel == "PlaceframeLeaseServerClient"


def test_command_spec_producer_runs_with_project_cwd(recorder: Recorder) -> None:
    producer: Callable[[Path], str] = SpecProducer("dotnet run -- dump-openapi")

    produced = producer(Path("services/api"))

    assert json.loads(produced) == RAW_SCHEMA
    assert recorder.commands == [("dotnet run -- dump-openapi", Path("services/api"), None)]


def test_spec_producer_overlays_env(recorder: Recorder) -> None:
    producer: Callable[[Path], str] = SpecProducer(
        "uv run --project . python -m src.dump_openapi", env={"CODEGEN": "1"}
    )

    producer(Path("docker/api"))

    assert recorder.commands == [
        ("uv run --project . python -m src.dump_openapi", Path("docker/api"), {"CODEGEN": "1"})
    ]
