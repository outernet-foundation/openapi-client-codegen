import json
from os import walk
from pathlib import Path
from shutil import copytree
from tempfile import NamedTemporaryFile, TemporaryDirectory

from bashrun.bash import bash

from .resources import CONFIGS_DIR, IGNORE_FILE, OPENAPI_GENERATOR_CLI_VERSION
from .naming import ClientNaming
from .unity import write_unity_package_metadata

_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")


def generate_client(
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
    if generator == "csharp" and templates_dir is None:
        msg = "csharp client generation requires templates_dir (call regenerate_templates first)"
        raise ValueError(msg)

    client_config = json.loads((CONFIGS_DIR / f"{generator}.json").read_text(encoding="utf-8"))

    if generator == "csharp":
        client_config["additionalProperties"]["packageName"] = names.camel
    else:
        client_config["additionalProperties"]["projectName"] = names.dashed
        client_config["additionalProperties"]["packageName"] = names.underscored

    with (
        NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as temporary_spec_file,
        NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as temporary_config_file,
        TemporaryDirectory() as temporary_directory_string,
    ):
        temporary_directory = Path(temporary_directory_string)

        # Force every operation onto a single "Default" tag so the generator emits one API class
        spec_json = json.loads(spec)
        for path_item in spec_json.get("paths", {}).values():
            for method in _HTTP_METHODS:
                operation = path_item.get(method)
                if isinstance(operation, dict):
                    operation["tags"] = ["Default"]

        json.dump(spec_json, temporary_spec_file)
        temporary_spec_file.flush()

        json.dump(client_config, temporary_config_file)
        temporary_config_file.flush()

        command = (
            f"uvx --from 'openapi-generator-cli[jdk4py]=={OPENAPI_GENERATOR_CLI_VERSION}' openapi-generator-cli generate "
            f"-g {generator} "
            f"-i {Path(temporary_spec_file.name).resolve().as_posix()} "
            f"-o {temporary_directory.resolve().as_posix()} "
            f"-c {Path(temporary_config_file.name).resolve().as_posix()} "
            f"--ignore-file-override {IGNORE_FILE.resolve().as_posix()} "
        )

        if generator == "csharp" and templates_dir is not None:
            command += f" -t {(templates_dir / 'csharp').resolve().as_posix()}"

        bash(command, env={"JAVA_OPTS": "-Dlog.level=warn"})

        print(f"Generated {generator} client (temp) at {temporary_directory}")

        if generator == "csharp":
            npm_name = None if npm_scope is None else f"{npm_scope}.{names.base.replace('-', '')}"
            write_unity_package_metadata(
                temporary_directory / "src" / names.camel,
                names.camel,
                extra_references,
                npm_name=npm_name,
                license_spdx=license_spdx,
                repository_url=repository_url,
            )

        print(f"Syncing to {output_dir}...")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Delete files that no longer exist in the freshly-generated tree
        for target_file in output_dir.rglob("*"):
            if not target_file.is_file():
                continue

            relative_path = target_file.relative_to(output_dir)

            # A Unity .meta file shadows a real file; map it back to decide staleness
            if target_file.name.endswith(".meta"):
                relative_path = relative_path.with_name(target_file.name[:-5])

            if not (temporary_directory / relative_path).exists():
                target_file.unlink()

        # Delete directories that no longer exist in the freshly-generated tree
        for root, directories, _ in walk(output_dir, topdown=False):
            for name in directories:
                target_directory = Path(root) / name
                if not (temporary_directory / target_directory.relative_to(output_dir)).exists():
                    target_directory.rmdir()

        copytree(temporary_directory, output_dir, dirs_exist_ok=True)

    if generator == "python":
        bash(f"uv pip install {output_dir.resolve().as_posix()}")
