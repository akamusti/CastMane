"""PyInstaller entry point for the CastMane AppImage.

Absolute import keeps the package context, so the relative imports
inside castmane (``from .app import ...``) keep working when frozen.
"""
from castmane.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
