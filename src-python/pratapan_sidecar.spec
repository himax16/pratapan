# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import subprocess
import sys
from pathlib import Path

import PyInstaller.config


def _target_triple() -> str:
    out = subprocess.check_output(["rustc", "-vV"], text=True)
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("could not determine rustc host triple")


triple = _target_triple()
out_name = f"pratapan-sidecar-{triple}"

_is_linux = sys.platform.startswith("linux")
_is_mac = sys.platform == "darwin"
_is_windows = sys.platform == "win32"

project_root = Path(SPECPATH).parent
dist_dir = project_root / "src-tauri" / "binaries"
dist_dir.mkdir(parents=True, exist_ok=True)

PyInstaller.config.CONF["distpath"] = str(dist_dir)

# Bundle all PySpark data files (JARs, JSON error defs, scripts, etc.)
_pyspark_spec = importlib.util.find_spec("pyspark")
if _pyspark_spec is None:
    raise RuntimeError("pyspark is not installed — run: uv sync")
_pyspark_dir = Path(_pyspark_spec.origin).parent

_pyspark_datas = []
for _src in _pyspark_dir.rglob("*"):
    if _src.is_file() and _src.suffix not in (".py", ".pyc"):
        _rel = _src.relative_to(_pyspark_dir.parent)
        _pyspark_datas.append((str(_src), str(_rel.parent)))

# Bundle the portable JRE so the frozen app doesn't need Java pre-installed
_jre_dir = project_root / "src-python" / "jre"
if not _jre_dir.is_dir():
    raise RuntimeError("JRE not found — run: pnpm jre:download")
_jre_datas = [(str(_jre_dir), "jre")]

a = Analysis(
    [str(project_root / "src-python" / "main.py")],
    pathex=[str(project_root / "src-python")],
    binaries=[],
    datas=_pyspark_datas + _jre_datas,
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "anyio",
        "anyio._backends._asyncio",
        "pyspark",
        "pyspark.sql",
        "pyspark.sql.session",
        "pyspark.sql.types",
        "pyspark.context",
        "pyspark.conf",
        "py4j",
        "py4j.java_gateway",
        "py4j.protocol",
        "py4j.java_collections",
    ],
    hookspath=[],
    runtime_hooks=[str(project_root / "src-python" / "runtime_hook_java.py")],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=out_name,
    debug=False,
    strip=_is_linux or _is_mac,
    upx=False,
    console=not _is_windows,
)
