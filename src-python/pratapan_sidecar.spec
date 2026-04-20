# -*- mode: python ; coding: utf-8 -*-
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

project_root = Path(SPECPATH).parent
dist_dir = project_root / "src-tauri" / "binaries"
dist_dir.mkdir(parents=True, exist_ok=True)

PyInstaller.config.CONF["distpath"] = str(dist_dir)

a = Analysis(
    [str(project_root / "src-python" / "main.py")],
    pathex=[str(project_root / "src-python")],
    binaries=[],
    datas=[],
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
    ],
    hookspath=[],
    runtime_hooks=[],
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
    strip=False,
    upx=False,
    console=True,
)
