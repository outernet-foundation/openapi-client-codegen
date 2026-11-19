import json
from pathlib import Path


def write_npm_package_metadata(
    package_json_path: Path,
    author: str | None = None,
    license_spdx: str | None = None,
    repository_url: str | None = None,
) -> None:
    if author is None and license_spdx is None and repository_url is None:
        return

    package = json.loads(package_json_path.read_text(encoding="utf-8"))

    if repository_url is not None:
        package["repository"] = {"type": "git", "url": repository_url}
    if author is not None:
        package["author"] = author
    if license_spdx is not None:
        package["license"] = license_spdx

    package_json_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
