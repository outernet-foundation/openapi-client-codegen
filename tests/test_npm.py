import json
from pathlib import Path

import pytest

from openapi_client_codegen import npm
from openapi_client_codegen.npm import generate_npm_lockfile, write_npm_package_metadata


def write_package(
    tmp_path: Path,
    author: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
    typescript_pin: str | None = None,
) -> tuple[Path, str]:
    original = (
        json.dumps(
            {
                "name": "@placeframe/api-client",
                "version": "0.1.0",
                "author": "OpenAPI-Generator",
                "repository": {"type": "git", "url": "https://github.com/GIT_USER_ID/GIT_REPO_ID.git"},
                "devDependencies": {"typescript": "^4.0 || ^5.0"},
            },
            indent=2,
        )
        + "\n"
    )
    package_json_path = tmp_path / "package.json"
    package_json_path.write_text(original, encoding="utf-8")
    write_npm_package_metadata(
        package_json_path,
        author=author,
        license_spdx=license_spdx,
        repository_url=repository_url,
        typescript_pin=typescript_pin,
    )
    return package_json_path, original


def test_rewrites_repository_author_and_license(tmp_path: Path) -> None:
    package_json_path, _ = write_package(
        tmp_path,
        author="placeframe",
        license_spdx="Apache-2.0",
        repository_url="https://github.com/outernet-foundation/placeframe.git",
    )
    package = json.loads(package_json_path.read_text(encoding="utf-8"))

    assert package["name"] == "@placeframe/api-client"
    assert package["repository"] == {"type": "git", "url": "https://github.com/outernet-foundation/placeframe.git"}
    assert package["author"] == "placeframe"
    assert package["license"] == "Apache-2.0"


def test_no_metadata_leaves_generated_manifest_untouched(tmp_path: Path) -> None:
    package_json_path, original = write_package(tmp_path)

    assert package_json_path.read_text(encoding="utf-8") == original


def test_typescript_pin_rewrites_dev_dependency_to_exact_version(tmp_path: Path) -> None:
    package_json_path, _ = write_package(tmp_path, typescript_pin="5.9.3")
    package = json.loads(package_json_path.read_text(encoding="utf-8"))

    assert package["devDependencies"]["typescript"] == "5.9.3"


def test_typescript_pin_adds_dev_dependencies_when_absent(tmp_path: Path) -> None:
    package_json_path = tmp_path / "package.json"
    package_json_path.write_text(json.dumps({"name": "@placeframe/api-client", "version": "0.1.0"}), encoding="utf-8")

    write_npm_package_metadata(package_json_path, typescript_pin="5.9.3")
    package = json.loads(package_json_path.read_text(encoding="utf-8"))

    assert package["devDependencies"] == {"typescript": "5.9.3"}


def test_generate_npm_lockfile_resolves_without_running_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[tuple[str, Path]] = []

    def fake_bash(command: str, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
        commands.append((command, cwd if cwd is not None else Path()))

    monkeypatch.setattr(npm, "bash", fake_bash)
    generate_npm_lockfile(tmp_path)

    assert commands == [("npm install --package-lock-only --ignore-scripts --no-audit --no-fund", tmp_path)]
