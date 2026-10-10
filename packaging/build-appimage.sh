#!/bin/bash
# Build CastMane-*.AppImage (x86_64).
# Usage:  ./packaging/build-appimage.sh
# Output: dist/CastMane-<version>-x86_64.AppImage
#
# What gets bundled vs. what stays on the host:
#   INSIDE : Python + PySide6 + dbus-next + app code (via PyInstaller onedir)
#   HOST   : ffmpeg, gst-launch-1.0 (+ pipewiresrc/openh264enc/matroskamux),
#            xdg-desktop-portal ScreenCast backend. Rationale: the Wayland
#            backend streams PipeWire fds from the host portal; a second
#            containerized GStreamer/PipeWire would break that handoff.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)"
[ -n "$VERSION" ] || VERSION="0.1.0"
ARCH="${ARCH:-x86_64}"
OUT="dist/CastMane-${VERSION}-${ARCH}.AppImage"
VENV="${VENV:-.venv-appimage}"

echo "==> [1/5] build venv ($VENV)"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q . pyinstaller

echo "==> [2/5] PyInstaller onedir"
rm -rf build dist/castmane
"$VENV/bin/pyinstaller" --noconfirm --clean \
  --distpath "$ROOT/dist" --workpath "$ROOT/build" \
  packaging/castmane.spec

echo "==> [3/5] assemble AppDir"
rm -rf AppDir
mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/256x256/apps
cp -r dist/castmane AppDir/usr/bin/castmane
cp packaging/AppRun AppDir/AppRun
cp packaging/castmane.desktop AppDir/castmane.desktop
cp packaging/castmane.desktop AppDir/usr/share/applications/
cp src/castmane/assets/logo.png AppDir/castmane.png
cp src/castmane/assets/logo.png AppDir/.DirIcon
cp src/castmane/assets/logo.png AppDir/usr/share/icons/hicolor/256x256/apps/castmane.png
cp LICENSE AppDir/ 2>/dev/null || true

echo "==> [4/5] appimagetool (official AppImage release, downloaded once)"
TOOL="packaging/tools/appimagetool-${ARCH}.AppImage"
if [ ! -x "$TOOL" ]; then
  mkdir -p packaging/tools
  curl -fL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
fi

echo "==> [5/5] build $OUT"
rm -f "$OUT"
ARCH="$ARCH" "$TOOL" AppDir "$OUT"
ls -lh "$OUT"
echo "Done. Test: ./$OUT (needs host ffmpeg + gstreamer + portal)"
