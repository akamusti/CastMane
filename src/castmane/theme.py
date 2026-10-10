"""Brand palette extracted from the CastMane logo.

Logo: indigo -> cyan monitor frame (#5B54F0 -> #43BFF2) with a purple
rec dot (#A855F7) on a deep navy background (#14172E).
"""
from __future__ import annotations

from pathlib import Path

BG_BASE = "#14172E"
BG_CARD = "#1E2342"
BG_INPUT = "#252B4D"
BORDER = "#2E3560"
BORDER_HOVER = "#3D457A"

TEXT_MAIN = "#E9ECF7"
TEXT_MUTED = "#9AA3C7"
TEXT_FAINT = "#7C86AB"

ACCENT_INDIGO = "#5B54F0"
ACCENT_CYAN = "#43BFF2"
ACCENT_PURPLE = "#A855F7"
ACCENT_GRADIENT = (
    f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    f"stop:0 {ACCENT_INDIGO}, stop:1 {ACCENT_CYAN})"
)

RECORD_RED = "#E5484D"
RECORD_RED_DARK = "#B3272E"

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


def logo_path() -> str | None:
    """Return the logo file path if bundled, else None."""
    return str(LOGO_PATH) if LOGO_PATH.is_file() else None
