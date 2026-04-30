from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType


def discover_bot_names(bots_dir: Path) -> list[str]:
    names = []
    for path in sorted(bots_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        names.append(path.stem)
    return names


def load_bot_module(package_prefix: str, bot_name: str) -> ModuleType:
    return importlib.import_module(f"{package_prefix}.{bot_name}")
