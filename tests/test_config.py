import importlib.metadata
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from openapi_client_codegen.orchestrator import DEV_SENTINEL, load_config


def write_config(tmp_path: Path, payload: dict[str, object]) -> Path:
    config_path = tmp_path / "openapi-client-codegen.yaml"
    config_path.write_text(
        yaml.safe_dump(payload, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def base_payload() -> dict[str, object]:
    return {
        "projects": {"docker/api": ["python"]},
        "root_name": "placeframe",
        "generated_root": "packages/generated",
        "spec_command": "uv run --project . python -m src.dump_openapi",
        "requires": ">=0.1",
    }


def _version_dev_sentinel(_name: str) -> str:
    return DEV_SENTINEL


def _version_0_1_18(_name: str) -> str:
    return "0.1.18"


def _version_0_1_19_dev5(_name: str) -> str:
    return "0.1.19.dev5"


def _version_0_1_17(_name: str) -> str:
    return "0.1.17"


def test_load_config_parses_yaml(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, base_payload()))

    assert config.projects == {"docker/api": ["python"]}
    assert config.root_name == "placeframe"
    assert config.requires == ">=0.1"


def test_requires_omitted_is_required(tmp_path: Path) -> None:
    payload = base_payload()
    del payload["requires"]

    with pytest.raises(ValidationError, match="requires"):
        load_config(write_config(tmp_path, payload))


def test_requires_empty_string_rejected(tmp_path: Path) -> None:
    payload = base_payload()
    payload["requires"] = ""

    with pytest.raises(ValidationError, match="requires"):
        load_config(write_config(tmp_path, payload))


def test_requires_dev_sentinel_skips_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _version_dev_sentinel)
    payload = base_payload()
    payload["requires"] = ">=0.1.18"

    config = load_config(write_config(tmp_path, payload))

    assert config.requires == ">=0.1.18"


def test_requires_in_range_loads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _version_0_1_18)
    payload = base_payload()
    payload["requires"] = ">=0.1.18"

    config = load_config(write_config(tmp_path, payload))

    assert config.requires == ">=0.1.18"


def test_requires_dev_channel_prerelease_satisfies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _version_0_1_19_dev5)
    payload = base_payload()
    payload["requires"] = ">=0.1.18"

    config = load_config(write_config(tmp_path, payload))

    assert config.requires == ">=0.1.18"


def test_requires_out_of_range_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", _version_0_1_17)
    payload = base_payload()
    payload["requires"] = ">=0.1.18"

    with pytest.raises(SystemExit, match="does not satisfy requires"):
        load_config(write_config(tmp_path, payload))


def test_requires_invalid_specifier_rejected(tmp_path: Path) -> None:
    payload = base_payload()
    payload["requires"] = "not-a-specifier"

    with pytest.raises(ValidationError, match="requires"):
        load_config(write_config(tmp_path, payload))
