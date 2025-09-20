"""Lazily proxy calls to the top-level :mod:`dynamic_crop` module."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_module: ModuleType | None = None


def _load() -> ModuleType:
    global _module
    if _module is None:
        _module = importlib.import_module("dynamic_crop")
    return _module


def __getattr__(name: str) -> Any:  # pragma: no cover - simple proxy
    return getattr(_load(), name)


def __dir__() -> list[str]:  # pragma: no cover - debug convenience
    return sorted(set(globals()) | set(dir(_load())))