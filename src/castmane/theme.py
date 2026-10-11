"""Design tokens for the CastMane window.

The default (light) palette is deliberately plain: one warm off-white
canvas, ink for anything primary, and a single saturated red that only
ever means "recording". No gradients, no glass, no glow — a hairline
does the separating, and colour is reserved for state so it keeps its
meaning. The dark palette keeps the same warm undertone so switching
themes never changes the app's character, only its brightness.
"""
from __future__ import annotations

from pathlib import Path

# --- Surfaces (warm paper) ---
CANVAS = "#F3F1ED"  # app background, sidebar, footer band
SURFACE = "#FFFFFF"  # header, settings pane
SURFACE_SUNKEN = "#EAE7E1"  # segmented track, slider groove
HAIRLINE = "#E3E0D9"  # 1px separators and quiet borders
HAIRLINE_STRONG = "#CFCAC1"  # borders that must read as an edge

# --- Text ---
TEXT_MAIN = "#1F1C19"  # ink
TEXT_SOFT = "#57524B"
TEXT_MUTED = "#857F76"
TEXT_FAINT = "#A8A29A"

# --- Ink controls (primary buttons, selected nav) ---
INK = "#1F1C19"
INK_HOVER = "#3B352F"
INK_PRESSED = "#12100E"
INK_TINT = "#EAE7E1"  # hover wash over the canvas
# Text drawn on top of INK (record button, selections).
PRIMARY_TEXT = "#FFFFFF"

# --- Buttons ---
BTN_BG = "#FFFFFF"
BTN_BORDER = "#D9D5CD"
BTN_HOVER = "#F1EFEA"
BTN_PRESSED = "#E7E4DD"
BTN_DISABLED_BG = "#F4F2EE"
BTN_DISABLED_TEXT = "#B4AFA7"

# --- Record: the only saturated colour in the UI ---
REC = "#C13227"
REC_HOVER = "#AA2B21"
REC_PRESSED = "#93241C"
REC_TINT = "#FBEDEB"
REC_BORDER = "#EBC7C1"

# --- Ready / paused states ---
READY = "#1F6B45"
READY_TINT = "#EAF3EE"
PAUSED = "#96600A"
PAUSED_TINT = "#FBF2E2"

# --- Metrics (px) ---
RADIUS = 7  # controls
RADIUS_SM = 5  # inner elements: segments, chips
RADIUS_LG = 9  # containers

HEADER_H = 52
SIDEBAR_W = 176
NAV_H = 34
FOOTER_H = 34
TRANSPORT_GAP = 14

# Horizontal padding of one settings row (left column + control column).
ROW_PAD_X = 20
ROW_PAD_Y = 11
# Width of the control column in the settings rows.
CONTROL_W = 236

# Inner padding of a segmented-control well around its buttons.
SEGMENT_PAD = 3
# Horizontal breathing room inside one segment button (QSS padding is 4+4,
# plus a cushion so a translated label never touches the rounded corner).
SEGMENT_TEXT_PAD = 24

# --- Fonts ---
# Desktop-native stacks first: Adwaita on GNOME, Cantarell on older GNOME,
# Ubuntu on Ubuntu, Noto/DejaVu everywhere else.
FONT_UI = (
    '"Adwaita Sans", "Cantarell", "Ubuntu", "Noto Sans", '
    '"DejaVu Sans", sans-serif'
)
# Monospace only for numbers that must not jitter: the timer, paths, version.
FONT_MONO = (
    '"JetBrains Mono", "DejaVu Sans Mono", "Noto Sans Mono", '
    '"Liberation Mono", monospace'
)

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"  # taskbar / desktop icon (navy original)
MARK_PATH = ASSETS_DIR / "mark.png"  # in-window header mark (ink + red)


def logo_path() -> str | None:
    """Return the desktop icon path if bundled, else None."""
    return str(LOGO_PATH) if LOGO_PATH.is_file() else None


def mark_path() -> str | None:
    """Return the in-window header mark path if bundled, else None."""
    return str(MARK_PATH) if MARK_PATH.is_file() else None


# --- Theme registry ---
# Every theme exposes the same keys: the colour names above plus
# PRIMARY_TEXT (text drawn on top of INK). Module-level constants stay
# as the light values for backwards compatibility; runtime code should
# go through get_theme() so a theme switch repaints everything.
SUPPORTED_THEMES = ("light", "dark")
DEFAULT_THEME = "light"

_LIGHT: dict[str, str] = {
    "CANVAS": CANVAS,
    "SURFACE": SURFACE,
    "SURFACE_SUNKEN": SURFACE_SUNKEN,
    "HAIRLINE": HAIRLINE,
    "HAIRLINE_STRONG": HAIRLINE_STRONG,
    "TEXT_MAIN": TEXT_MAIN,
    "TEXT_SOFT": TEXT_SOFT,
    "TEXT_MUTED": TEXT_MUTED,
    "TEXT_FAINT": TEXT_FAINT,
    "INK": INK,
    "INK_HOVER": INK_HOVER,
    "INK_PRESSED": INK_PRESSED,
    "INK_TINT": INK_TINT,
    "PRIMARY_TEXT": PRIMARY_TEXT,
    "BTN_BG": BTN_BG,
    "BTN_BORDER": BTN_BORDER,
    "BTN_HOVER": BTN_HOVER,
    "BTN_PRESSED": BTN_PRESSED,
    "BTN_DISABLED_BG": BTN_DISABLED_BG,
    "BTN_DISABLED_TEXT": BTN_DISABLED_TEXT,
    "REC": REC,
    "REC_HOVER": REC_HOVER,
    "REC_PRESSED": REC_PRESSED,
    "REC_TINT": REC_TINT,
    "REC_BORDER": REC_BORDER,
    "READY": READY,
    "READY_TINT": READY_TINT,
    "PAUSED": PAUSED,
    "PAUSED_TINT": PAUSED_TINT,
}

# Warm dark: same character, inverted brightness. The primary button
# turns light so it keeps standing out; PRIMARY_TEXT flips with it.
_DARK: dict[str, str] = {
    "CANVAS": "#201D1A",
    "SURFACE": "#2A2622",
    "SURFACE_SUNKEN": "#171412",
    "HAIRLINE": "#3B352F",
    "HAIRLINE_STRONG": "#5A534B",
    "TEXT_MAIN": "#F1ECE5",
    "TEXT_SOFT": "#C8C0B4",
    "TEXT_MUTED": "#A29A8D",
    "TEXT_FAINT": "#6B655C",
    "INK": "#EDE7DE",
    "INK_HOVER": "#FFFFFF",
    "INK_PRESSED": "#D5CFC4",
    "INK_TINT": "#342F29",
    "PRIMARY_TEXT": "#1F1C19",
    "BTN_BG": "#2A2622",
    "BTN_BORDER": "#453F37",
    "BTN_HOVER": "#342F29",
    "BTN_PRESSED": "#2C2721",
    "BTN_DISABLED_BG": "#242019",
    "BTN_DISABLED_TEXT": "#5E584F",
    "REC": "#D65347",
    "REC_HOVER": "#C04437",
    "REC_PRESSED": "#A5372C",
    "REC_TINT": "#3D231F",
    "REC_BORDER": "#6B362E",
    "READY": "#5FAE7E",
    "READY_TINT": "#1C2B23",
    "PAUSED": "#D9A648",
    "PAUSED_TINT": "#332917",
}

THEMES: dict[str, dict[str, str]] = {"light": _LIGHT, "dark": _DARK}


def normalize_theme(name: str) -> str:
    """Clamp any input to a supported theme name."""
    short = (name or "").strip().lower()
    return short if short in THEMES else DEFAULT_THEME


def get_theme(name: str) -> dict[str, str]:
    """Return a mutable copy of the named theme's colour table."""
    return dict(THEMES.get(normalize_theme(name), _LIGHT))
