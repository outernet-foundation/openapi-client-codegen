import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from openapi_client_codegen import cli
from openapi_client_codegen.cli import app
from openapi_client_codegen.orchestrator import ProjectsConfig

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
}


class Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def fake_generate_projects(self, config: ProjectsConfig, **kwargs: object) -> None:
        self.calls.append({"config": config, **kwargs})


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(cli, "generate_projects", recorder.fake_generate_projects)
    return recorder


def write_config(directory: Path, settings: dict[str, object]) -> Path:
    config = directory / "clients.json"
    config.write_text(json.dumps(settings), encoding="utf-8")
    return config


def test_single_command_app_passes_the_validated_model(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, FULL_SETTINGS)

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code == 0
    call = recorder.calls[0]
    assert call["config"] == ProjectsConfig.model_validate(FULL_SETTINGS)


def test_filter_flags_pass_through(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, FULL_SETTINGS)

    result = runner.invoke(
        app,
        ["--config", str(config), "--project", "docker/api", "--client", "csharp", "--no-cache"],
    )

    assert result.exit_code == 0
    call = recorder.calls[0]
    assert call["project"] == "docker/api"
    assert call["client"] == "csharp"
    assert call["no_cache"] is True


def test_unknown_config_key_fails_loudly(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, {"projects": {}, "rot_name": "placeframe"})

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "rot_name" in result.output
    assert recorder.calls == []


def test_missing_projects_mapping_fails(tmp_path: Path, recorder: Recorder) -> None:
    config = write_config(tmp_path, {"root_name": "placeframe"})

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "projects" in result.output
    assert recorder.calls == []


def test_missing_required_field_fails(tmp_path: Path, recorder: Recorder) -> None:
    settings = dict(FULL_SETTINGS)
    del settings["spec_command"]
    config = write_config(tmp_path, settings)

    result = runner.invoke(app, ["--config", str(config)])

    assert result.exit_code != 0
    assert "spec_command" in result.output
    assert recorder.calls == []
