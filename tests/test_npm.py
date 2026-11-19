import json
from pathlib import Path

from openapi_client_codegen.npm import write_npm_package_metadata


def write_package(
    tmp_path: Path,
    author: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
) -> tuple[Path, str]:
    original = (
        json.dumps(
            {
                "name": "@placeframe/api-client",
                "version": "0.1.0",
                "author": "OpenAPI-Generator",
                "repository": {"type": "git", "url": "https://github.com/GIT_USER_ID/GIT_REPO_ID.git"},
            },
            indent=2,
        )
        + "\n"
    )
    package_json_path = tmp_path / "package.json"
    package_json_path.write_text(original, encoding="utf-8")
    write_npm_package_metadata(
        package_json_path, author=author, license_spdx=license_spdx, repository_url=repository_url
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
