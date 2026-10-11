"""Brand palette extracted from the CastMane logo.

Logo: indigo -> cyan monitor frame (#5B54F0 -> #43BFF2) with a purple
rec dot (#A855F7) on a deep navy background (#14172E).
"""
from __future__ import annotations

from pathlib import Path

# --- Surfaces ---
BG_BASE = "#14172E"
BG_CARD = "#1E2342"
BG_INPUT = "#252B4D"
BG_SUNKEN = "#181C36"
BORDER = "#2E3560"
BORDER_HOVER = "#3D457A"

# --- Text ---
TEXT_MAIN = "#E9ECF7"
TEXT_MUTED = "#9AA3C7"
TEXT_FAINT = "#7C86AB"
TEXT_DISABLED = "#565E86"

# --- Accents ---
ACCENT_INDIGO = "#5B54F0"
ACCENT_CYAN = "#43BFF2"
ACCENT_PURPLE = "#A855F7"
ACCENT_GRADIENT = (
    f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    f"stop:0 {ACCENT_INDIGO}, stop:1 {ACCENT_CYAN})"
)
# Dimmed variant for resting segmented controls.
ACCENT_GRADIENT_SOFT = (
    f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    f"stop:0 #2A2F63, stop:1 #23395A)"
)

# --- Recording state (stop / error red) ---
RECORD_RED = "#E5484D"
RECORD_RED_DARK = "#B3272E"
RECORD_BG = "#8C2F2A"
RECORD_BG_HOVER = "#9D3630"
RECORD_BORDER = "#A83C35"

# --- Interaction ---
BG_HOVER = "#2D3459"
BG_PRESSED = "#20264A"
BG_DISABLED = "#1A1F3A"

# --- Metrics (px) ---
RADIUS_CARD = 16
RADIUS_CONTROL = 10
RADIUS_SMALL = 8

# --- Fonts ---
FONT_UI = '"Noto Sans", "DejaVu Sans", "Liberation Sans", sans-serif'
FONT_MONO = '"Noto Sans Mono", "DejaVu Sans Mono", "Liberation Mono", monospace'

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"


def logo_path() -> str | None:
    """Return the logo file path if bundled, else None."""
    return str(LOGO_PATH) if LOGO_PATH.is_file() else None
