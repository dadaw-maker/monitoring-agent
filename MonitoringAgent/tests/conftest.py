"""Test helpers.

The three services each ship a top-level `app` package with the same name
(by design — every service's Dockerfile copies its own `app/` to `/app/app`
in isolation). To unit-test more than one service in the same pytest run we
import them one at a time, purging `sys.modules['app']` and adjusting
`sys.path` between imports so each import resolves against the intended
service directory.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"


def import_service_module(service_dir: str, module: str):
    service_path = ROOT / "services" / service_dir
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]

    if str(LIBS) not in sys.path:
        sys.path.insert(0, str(LIBS))

    sys.path = [p for p in sys.path if p != str(service_path)]
    sys.path.insert(0, str(service_path))

    return importlib.import_module(f"app.{module}")
