"""Design tokens for the CastMane window.

The default (light) palette is deliberately plain: one warm off-white
canvas, ink for anything primary, and a single saturated red that only
ever means "recording". No gradients, no glass, no glow — a hairline
does the separating, and colour is reserved for state so it keeps its
meaning. The other themes keep the same layout idiom and only change
the palette: dark is the warm dark twin, ocean a cool light blue,
midnight a deep navy night, forest a deep moss night, dracula the
official Dracula palette, nord the official Nord polar night.
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

# Switch knob: always white in the light theme (dark track when on).
# Dark themes flip the ON knob to ink so it reads on a light track.
SWITCH_KNOB_OFF = "#FFFFFF"
SWITCH_KNOB_ON = "#FFFFFF"

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
# PRIMARY_TEXT (text drawn on top of INK) and SWITCH_KNOB_OFF/ON
# (knob fill when the toggle is off/on). Module-level constants stay
# as the light values for backwards compatibility; runtime code should
# go through get_theme() so a theme switch repaints everything.
SUPPORTED_THEMES = ("light", "dark", "ocean", "midnight", "forest", "dracula", "nord")
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
    "SWITCH_KNOB_OFF": SWITCH_KNOB_OFF,
    "SWITCH_KNOB_ON": SWITCH_KNOB_ON,
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
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#1F1C19",
}

# Cool light blue: same layout idiom, ink turns deep sea-blue so the
# primary button keeps standing out on the pale canvas.
_OCEAN: dict[str, str] = {
    "CANVAS": "#EAF0F4",
    "SURFACE": "#FFFFFF",
    "SURFACE_SUNKEN": "#DEE7ED",
    "HAIRLINE": "#D2DCE4",
    "HAIRLINE_STRONG": "#ACBECB",
    "TEXT_MAIN": "#1A2A36",
    "TEXT_SOFT": "#465A6A",
    "TEXT_MUTED": "#6E8595",
    "TEXT_FAINT": "#9AADB9",
    "INK": "#1C4A63",
    "INK_HOVER": "#2A5B77",
    "INK_PRESSED": "#14384C",
    "INK_TINT": "#DCE7EE",
    "PRIMARY_TEXT": "#FFFFFF",
    "BTN_BG": "#FFFFFF",
    "BTN_BORDER": "#C6D3DD",
    "BTN_HOVER": "#E3EBF1",
    "BTN_PRESSED": "#D3DFE8",
    "BTN_DISABLED_BG": "#EDF1F4",
    "BTN_DISABLED_TEXT": "#A6B7C2",
    "REC": "#C13227",
    "REC_HOVER": "#AA2B21",
    "REC_PRESSED": "#93241C",
    "REC_TINT": "#FBEDEB",
    "REC_BORDER": "#EBC7C1",
    "READY": "#1F6B45",
    "READY_TINT": "#EAF3EE",
    "PAUSED": "#96600A",
    "PAUSED_TINT": "#FBF2E2",
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#FFFFFF",
}

# Deep navy night: the dark idiom on a blue canvas. Primary turns
# pale so it keeps standing out; the knob flips to ink when on.
_MIDNIGHT: dict[str, str] = {
    "CANVAS": "#141924",
    "SURFACE": "#1E2534",
    "SURFACE_SUNKEN": "#0E131D",
    "HAIRLINE": "#2E3749",
    "HAIRLINE_STRONG": "#4A5875",
    "TEXT_MAIN": "#E9EDF5",
    "TEXT_SOFT": "#B9C3D4",
    "TEXT_MUTED": "#8D99AF",
    "TEXT_FAINT": "#5B6579",
    "INK": "#D7E3F7",
    "INK_HOVER": "#FFFFFF",
    "INK_PRESSED": "#B7C7E3",
    "INK_TINT": "#28324A",
    "PRIMARY_TEXT": "#141924",
    "BTN_BG": "#1E2534",
    "BTN_BORDER": "#39445C",
    "BTN_HOVER": "#28324A",
    "BTN_PRESSED": "#222A3D",
    "BTN_DISABLED_BG": "#181E2B",
    "BTN_DISABLED_TEXT": "#525D74",
    "REC": "#E06A5E",
    "REC_HOVER": "#C9584D",
    "REC_PRESSED": "#A84840",
    "REC_TINT": "#37211F",
    "REC_BORDER": "#6E3B36",
    "READY": "#6FBF8F",
    "READY_TINT": "#1A2B24",
    "PAUSED": "#D9A648",
    "PAUSED_TINT": "#332917",
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#141924",
}

# Deep moss night: the dark idiom on a green canvas.
_FOREST: dict[str, str] = {
    "CANVAS": "#191F1B",
    "SURFACE": "#222B24",
    "SURFACE_SUNKEN": "#111612",
    "HAIRLINE": "#333F34",
    "HAIRLINE_STRONG": "#55664F",
    "TEXT_MAIN": "#EBEFE6",
    "TEXT_SOFT": "#BEC8B7",
    "TEXT_MUTED": "#93A088",
    "TEXT_FAINT": "#66705F",
    "INK": "#DFE8D5",
    "INK_HOVER": "#FFFFFF",
    "INK_PRESSED": "#C0CBAE",
    "INK_TINT": "#2C352C",
    "PRIMARY_TEXT": "#191F1B",
    "BTN_BG": "#222B24",
    "BTN_BORDER": "#3E4C3D",
    "BTN_HOVER": "#2C352C",
    "BTN_PRESSED": "#252D26",
    "BTN_DISABLED_BG": "#1B211C",
    "BTN_DISABLED_TEXT": "#5A6656",
    "REC": "#DE6F60",
    "REC_HOVER": "#C75D50",
    "REC_PRESSED": "#A94D42",
    "REC_TINT": "#38211E",
    "REC_BORDER": "#6E3B34",
    "READY": "#71BE8A",
    "READY_TINT": "#1B2B22",
    "PAUSED": "#D9A648",
    "PAUSED_TINT": "#332917",
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#191F1B",
}

# Dracula night: official palette (background #282A36, foreground
# #F8F8F2, comment #6272A4). Primary turns purple so it keeps
# standing out; record uses Dracula red, ready uses Dracula green.
_DRACULA: dict[str, str] = {
    "CANVAS": "#282A36",
    "SURFACE": "#343746",
    "SURFACE_SUNKEN": "#21222C",
    "HAIRLINE": "#44475A",
    "HAIRLINE_STRONG": "#6272A4",
    "TEXT_MAIN": "#F8F8F2",
    "TEXT_SOFT": "#D8D8D2",
    "TEXT_MUTED": "#9EA0B8",
    "TEXT_FAINT": "#6272A4",
    "INK": "#BD93F9",
    "INK_HOVER": "#CFA9FA",
    "INK_PRESSED": "#A67FE0",
    "INK_TINT": "#3A3350",
    "PRIMARY_TEXT": "#282A36",
    "BTN_BG": "#343746",
    "BTN_BORDER": "#4A4E66",
    "BTN_HOVER": "#3E4158",
    "BTN_PRESSED": "#383B50",
    "BTN_DISABLED_BG": "#2B2E3B",
    "BTN_DISABLED_TEXT": "#5A5E7A",
    "REC": "#FF5555",
    "REC_HOVER": "#E64747",
    "REC_PRESSED": "#C93B3B",
    "REC_TINT": "#3D262B",
    "REC_BORDER": "#6E3A40",
    "READY": "#50FA7B",
    "READY_TINT": "#1E3325",
    "PAUSED": "#F1FA8C",
    "PAUSED_TINT": "#35331C",
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#282A36",
}

# Nord night: official polar-night canvas (#2E3440) with frost cyan
# as the primary; record uses Nord aurora red, ready uses Nord green.
_NORD: dict[str, str] = {
    "CANVAS": "#2E3440",
    "SURFACE": "#3B4252",
    "SURFACE_SUNKEN": "#242933",
    "HAIRLINE": "#434C5E",
    "HAIRLINE_STRONG": "#66718A",
    "TEXT_MAIN": "#ECEFF4",
    "TEXT_SOFT": "#D8DEE9",
    "TEXT_MUTED": "#A3ADC0",
    "TEXT_FAINT": "#76809A",
    "INK": "#88C0D0",
    "INK_HOVER": "#9ACEDB",
    "INK_PRESSED": "#6FA9BC",
    "INK_TINT": "#31414E",
    "PRIMARY_TEXT": "#2E3440",
    "BTN_BG": "#3B4252",
    "BTN_BORDER": "#4C566A",
    "BTN_HOVER": "#434C5E",
    "BTN_PRESSED": "#373E4D",
    "BTN_DISABLED_BG": "#2A303C",
    "BTN_DISABLED_TEXT": "#5A6577",
    "REC": "#D0757E",
    "REC_HOVER": "#BC636C",
    "REC_PRESSED": "#A1555D",
    "REC_TINT": "#3A2A2E",
    "REC_BORDER": "#6B4147",
    "READY": "#A3BE8C",
    "READY_TINT": "#232E21",
    "PAUSED": "#EBCB8B",
    "PAUSED_TINT": "#35301E",
    "SWITCH_KNOB_OFF": "#FFFFFF",
    "SWITCH_KNOB_ON": "#2E3440",
}

THEMES: dict[str, dict[str, str]] = {
    "light": _LIGHT,
    "dark": _DARK,
    "ocean": _OCEAN,
    "midnight": _MIDNIGHT,
    "forest": _FOREST,
    "dracula": _DRACULA,
    "nord": _NORD,
}


def normalize_theme(name: str) -> str:
    """Clamp any input to a supported theme name."""
    short = (name or "").strip().lower()
    return short if short in THEMES else DEFAULT_THEME


def get_theme(name: str) -> dict[str, str]:
    """Return a mutable copy of the named theme's colour table."""
    return dict(THEMES.get(normalize_theme(name), _LIGHT))


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a `#RRGGBB` colour (0 = black)."""
    hex_color = hex_color.strip().lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def surface_is_dark(t: dict[str, str]) -> bool:
    """True when the theme's surface is dark (ink artwork needs a tile)."""
    try:
        return _relative_luminance(t["SURFACE"]) < 0.4
    except (KeyError, ValueError):
        return False
