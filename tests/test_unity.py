import json
from pathlib import Path

from openapi_clientgen import write_unity_package_metadata


def write_package(
    tmp_path: Path,
    package_name: str = "PlaceframeApiClient",
    npm_name: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
) -> Path:
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    (package_dir / f"{package_name}.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk" />', encoding="utf-8")
    write_unity_package_metadata(
        package_dir, package_name, npm_name=npm_name, license_spdx=license_spdx, repository_url=repository_url
    )
    return package_dir


def test_keeps_csproj_and_redirects_build_output(tmp_path: Path):
    package_dir = write_package(tmp_path)

    assert (package_dir / "PlaceframeApiClient.csproj").exists()

    props = (package_dir / "Directory.Build.props").read_text(encoding="utf-8")
    assert "$(MSBuildThisFileDirectory)../../obj/$(MSBuildProjectName)/" in props
    assert "$(MSBuildThisFileDirectory)../../bin/$(MSBuildProjectName)/" in props


def test_manifest_defaults(tmp_path: Path):
    package_dir = write_package(tmp_path)
    package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))

    assert package["name"] == "org.nuget.placeframeapiclient"
    assert package["displayName"] == "PlaceframeApiClient"
    assert package["version"] == "0.0.0-local"
    assert package["dependencies"] == {
        "com.unity.nuget.newtonsoft-json": "3.x",
        "org.nuget.polly": "8.x",
        "org.nuget.jsonsubtypes": "2.x",
    }
    assert "license" not in package
    assert "repository" not in package


def test_manifest_npm_name_license_repository(tmp_path: Path):
    package_dir = write_package(
        tmp_path,
        npm_name="org.outernet.placeframe.apiclient",
        license_spdx="Apache-2.0",
        repository_url="https://github.com/outernet-foundation/placeframe.git",
    )
    package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))

    assert package["name"] == "org.outernet.placeframe.apiclient"
    assert package["license"] == "Apache-2.0"
    assert package["repository"] == {"type": "git", "url": "https://github.com/outernet-foundation/placeframe.git"}


def test_asmdef_references_base_set(tmp_path: Path):
    package_dir = write_package(tmp_path)
    asmdef = json.loads((package_dir / "PlaceframeApiClient.asmdef").read_text(encoding="utf-8"))

    assert asmdef["name"] == "PlaceframeApiClient"
    assert asmdef["references"] == ["Newtonsoft.Json", "Polly", "JsonSubTypes"]
