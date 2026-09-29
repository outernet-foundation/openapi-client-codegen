import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from openapi_client_codegen import cli, orchestrator
from openapi_client_codegen.cli import app
from openapi_client_codegen.orchestrator import ClientNaming

runner = CliRunner()

FULL_SETTINGS: dict[str, object] = {
    "projects": {"docker/api": ["python", "csharp"]},
    "root_name": "placeframe",
    "generated_root": "packages/generated",
    "spec_command": "uv run --project . python -m src.dump_openapi",
    "spec_env": {"CODEGEN": "1"},
    "npm_scope": "org.example.placeframe",
    "license_spdx": "Apache-2.0",
    "repository_url": "https://github.com/org/repo.git",
    "requires": ">=0.1",
}


class Recorder:
    def __init__(self) -> None:
        self.generated: list[tuple[str, Path]] = []
        self.git_commands: list[str] = []
        self.git_dirty = False

    def fake_bash_output(self, command: str, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
        return json.dumps({"openapi": "3.1.0", "info": {"title": "demo", "version": "0.0.0"}, "paths": {}})

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
        self.generated.append((generator, output_dir))

    def fake_git_status(self, command: str, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
        self.git_commands.append(command)
        return "M packages/generated/dummy\n" if self.git_dirty else ""

    def fake_git_diff(self, command: str, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
        self.git_commands.append(command)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(orchestrator, "bash_output", recorder.fake_bash_output)
    monkeypatch.setattr(cli, "regenerate_templates", recorder.fake_regenerate_templates)
    monkeypatch.setattr(cli, "generate_client", recorder.fake_generate_client)
    monkeypatch.setattr(cli, "bash_output", recorder.fake_git_status)
    monkeypatch.setattr(cli, "bash", recorder.fake_git_diff)
    return recorder


def write_config(directory: Path, settings: dict[str, object]) -> Path:
    config = directory / "clients.yaml"
    config.write_text(yaml.safe_dump(settings, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return config


def test_filter_flags_restrict_generation(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, FULL_SETTINGS)
    (tmp_path / "docker" / "api").mkdir(parents=True)

    result = runner.invoke(
        app,
        ["--config", str(config), "--root", str(tmp_path), "--project", "docker/api", "--client", "csharp"],
    )

    assert result.exit_code == 0
    assert recorder.generated == [("csharp", Path("packages/generated") / "csharp" / "api-client")]


def test_unknown_config_key_fails_loudly(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, {"projects": {"docker/api": ["python"]}, "rot_name": "placeframe"})

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "rot_name" in str(result.exception)
    assert recorder.generated == []


def test_missing_projects_mapping_fails(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, {"root_name": "placeframe"})

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "projects" in str(result.exception)
    assert recorder.generated == []


def test_missing_required_field_fails(tmp_path: Path, recorder: Recorder) -> None:
    settings = dict(FULL_SETTINGS)
    del settings["spec_command"]
    config = write_config(tmp_path, settings)

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "spec_command" in str(result.exception)
    assert recorder.generated == []


def test_check_forces_regen_and_passes_when_clean(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, FULL_SETTINGS)
    (tmp_path / "docker" / "api").mkdir(parents=True)

    result = runner.invoke(app, ["--config", str(config), "--root", str(tmp_path), "--check"])

    assert result.exit_code == 0
    assert [generator for generator, _ in recorder.generated] == ["python", "csharp"]
    assert recorder.git_commands == ["git status --porcelain -- docker/api/openapi.json packages/generated"]


def test_check_fails_when_tree_stale(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, FULL_SETTINGS)
    (tmp_path / "docker" / "api").mkdir(parents=True)
    recorder.git_dirty = True

    result = runner.invoke(app, ["--config", str(config), "--root", str(tmp_path), "--check"])

    assert result.exit_code != 0
    assert recorder.git_commands == [
        "git status --porcelain -- docker/api/openapi.json packages/generated",
        "git diff -- docker/api/openapi.json packages/generated",
    ]
