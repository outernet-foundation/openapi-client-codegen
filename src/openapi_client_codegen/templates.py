from pathlib import Path

from bashrun.bash import bash

from .resources import OPENAPI_GENERATOR_CLI_VERSION, SHIPPED_PATCHES_DIR


def regenerate_templates(target_dir: Path, extra_patches_dir: Path | None = None) -> None:
    csharp_target = target_dir / "csharp"
    csharp_target.mkdir(parents=True, exist_ok=True)

    bash(
        f"uvx --from 'openapi-generator-cli[jdk4py]=={OPENAPI_GENERATOR_CLI_VERSION}' "
        f"openapi-generator-cli author template -g csharp --library httpclient "
        f"-o {csharp_target.resolve().as_posix()}",
        env={"JAVA_OPTS": "-Dlog.level=warn"},
    )

    patch_directories = [SHIPPED_PATCHES_DIR]
    if extra_patches_dir is not None:
        patch_directories.append(extra_patches_dir)

    # Patches carry generic `csharp/...` paths; applying with cwd=target_dir and -p1 lands them on
    # the authored tree without needing a surrounding git repository.
    for patch_directory in patch_directories:
        for patch_file in sorted(patch_directory.glob("*.patch")):
            bash(
                f"git apply --ignore-space-change --ignore-whitespace -p1 {patch_file.resolve().as_posix()}",
                cwd=target_dir,
            )
