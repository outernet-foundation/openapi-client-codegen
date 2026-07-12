from pathlib import Path

OPENAPI_GENERATOR_CLI_VERSION = "7.22.0"

_DATA_DIR = Path(__file__).parent / "_data"
CONFIGS_DIR = _DATA_DIR / "configs"
IGNORE_FILE = _DATA_DIR / "openapi-generator-ignore"
SHIPPED_PATCHES_DIR = _DATA_DIR / "templates-patches" / "csharp"
