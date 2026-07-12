import json
from pathlib import Path

BASE_REFERENCES = ["Newtonsoft.Json", "Polly", "JsonSubTypes", "UniTask"]


def write_unity_package_metadata(
    package_dir: Path, package_name: str, extra_references: list[str] | None = None
) -> None:
    references = BASE_REFERENCES if not extra_references else [*BASE_REFERENCES, *extra_references]

    (package_dir / "package.json").write_text(
        json.dumps(
            {
                "name": f"org.nuget.{package_name.lower()}",
                "displayName": package_name,
                "version": "0.0.1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
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

    # Strip MSBuild project files: Unity consumes via .asmdef, not csproj. Leaving them in the UPM
    # package lets IDEs auto-build inside the immutable PackageCache, which writes bin/obj/ that Unity
    # then errors on for missing .meta files.
    for stale_artifact in (*package_dir.glob("*.csproj"), *package_dir.glob("Directory.Build.*")):
        stale_artifact.unlink()
