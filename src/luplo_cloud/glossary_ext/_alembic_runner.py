"""Console-script entry points for shipping the alembic partition via wheel.

`lps-ext-bootstrap` and `lps-ext-migrate` are exposed in pyproject.toml.
The bundled `alembic_luplo_ext.ini` is located via __file__ traversal —
this file lives at `<site-packages>/luplo_cloud/glossary_ext/_alembic_runner.py`,
so 3 parents up reaches `<site-packages>/`, where the ini is force-included
by hatch (see pyproject.toml [tool.hatch.build.targets.wheel.force-include]).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from luplo_cloud.glossary_ext._bootstrap import main as _bootstrap_main


def _ini_path() -> str:
    # _alembic_runner.py → glossary_ext/ → luplo_cloud/ → site-packages/
    site_packages = Path(__file__).resolve().parent.parent.parent
    ini = site_packages / "alembic_luplo_ext.ini"
    if not ini.exists():
        raise SystemExit(
            f"alembic_luplo_ext.ini not found at {ini} — wheel build is missing "
            "force-include for alembic_luplo_ext.ini and alembic_luplo_ext/."
        )
    return str(ini)


def bootstrap() -> int:
    return _bootstrap_main()


def migrate() -> int:
    if not os.environ.get("LUPLO_EXT_DB_URL") and not os.environ.get("LUPLO_DB_URL"):
        print("[lps-ext-migrate] LUPLO_EXT_DB_URL/LUPLO_DB_URL must be set",
              file=sys.stderr)
        return 1
    return subprocess.call(["alembic", "-c", _ini_path(), "upgrade", "head"])
