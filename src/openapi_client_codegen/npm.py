import json
from pathlib import Path

from bashrun.bash import bash


def write_npm_package_metadata(
    package_json_path: Path,
    author: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
    typescript_pin: str | None = None,
) -> None:
    if all(argument is None for argument in (author, license_spdx, repository_url, typescript_pin)):
        return

    package = json.loads(package_json_path.read_text(encoding="utf-8"))

    if repository_url is not None:
        package["repository"] = {"type": "git", "url": repository_url}
    if author is not None:
        package["author"] = author
    if license_spdx is not None:
        package["license"] = license_spdx
    if typescript_pin is not None:
        package.setdefault("devDependencies", {})["typescript"] = typescript_pin

    package_json_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")


def generate_npm_lockfile(package_dir: Path) -> None:
    # --ignore-scripts: lockfile resolution must not run the package's own prepare hook,
    # which invokes tsc before any toolchain exists at generation time
    bash("npm install --package-lock-only --ignore-scripts --no-audit --no-fund", cwd=package_dir)
