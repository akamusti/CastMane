# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CastMane AppImage.

Builds an onedir bundle (preferred AppImage input: everything the app
needs from PyPI is inside, host only provides ffmpeg / GStreamer /
xdg-desktop-portal which cannot be sensibly containerized for a
portal-based recorder).
"""
import os
from pathlib import Path

SPEC_DIR = Path(os.path.abspath(SPECDIR)) if "SPECDIR" in globals() else Path.cwd() / "packaging"
ROOT = SPEC_DIR.parent
SRC = ROOT / "src"

a = Analysis(
    [str(SPEC_DIR / "app_entry.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(SRC / "castmane" / "assets"), "castmane/assets")],
    hiddenimports=["dbus_next", "dbus_next.aio"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="castmane",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="castmane",
)
