import json
from pathlib import Path

BASE_REFERENCES = ["Newtonsoft.Json", "Polly", "JsonSubTypes"]

# UPM dual of BASE_REFERENCES: the asmdef compiles against the assembly names, the manifest
# resolves the same runtime support as packages. Newtonsoft maps to the Unity-blessed package
# instead of the UnityNuGet mirror identity, which collides with the assembly Unity itself
# provides. Exact versions, not ranges: UPM's package.json dependencies accept SemVer values
# only — the resolver rejects every range syntax (comparators, x-wildcards) with "Version 'X'
# is invalid" — and it treats a value as a minimum when resolving, so consumer manifests
# carrying newer minors still resolve without conflict.
BASE_DEPENDENCIES = {
    "com.unity.nuget.newtonsoft-json": "3.2.1",
    "org.nuget.polly": "8.1.0",
    "org.nuget.jsonsubtypes": "2.0.1",
}

# The csproj stays in the package (it is the nuget pack input), so MSBuild output is redirected
# two levels up, outside the package root: bin/obj inside a UPM package lack .meta files (Unity
# errors on import) and would ride the npm tarball. Two levels up is the client grouping dir in
# a repo checkout and Unity's Library/ (asset-import-invisible) under PackageCache consumption.
DIRECTORY_BUILD_PROPS = """<Project>
  <PropertyGroup>
    <BaseIntermediateOutputPath>$(MSBuildThisFileDirectory)../../obj/$(MSBuildProjectName)/</BaseIntermediateOutputPath>
    <BaseOutputPath>$(MSBuildThisFileDirectory)../../bin/$(MSBuildProjectName)/</BaseOutputPath>
  </PropertyGroup>
</Project>
"""


def write_unity_package_metadata(
    package_dir: Path,
    package_name: str,
    extra_references: list[str] | None = None,
    npm_name: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
) -> None:
    references = BASE_REFERENCES if not extra_references else [*BASE_REFERENCES, *extra_references]

    manifest: dict[str, object] = {
        "name": npm_name if npm_name is not None else f"org.nuget.{package_name.lower()}",
        "displayName": package_name,
        "version": "0.0.0-local",
        "dependencies": BASE_DEPENDENCIES,
    }
    if license_spdx is not None:
        manifest["license"] = license_spdx
    if repository_url is not None:
        manifest["repository"] = {"type": "git", "url": repository_url}

    (package_dir / "package.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (package_dir / f"{package_name}.asmdef").write_text(
        json.dumps(
            {
                "name": package_name,
                "references": references,
                "includePlatforms": [],
                "excludePlatforms": [],
                "allowUnsafeCode": False,
                "overrideReferences": False,
                "precompiledReferences": [],
                "autoReferenced": True,
                "defineConstraints": [],
                "versionDefines": [],
                "noEngineReferences": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Tell the C# compiler to enable nullable annotations
    (package_dir / "csc.rsp").write_text("-nullable:annotations", encoding="utf-8")
    (package_dir / "Directory.Build.props").write_text(DIRECTORY_BUILD_PROPS, encoding="utf-8")
