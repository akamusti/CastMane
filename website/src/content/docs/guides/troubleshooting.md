---
title: Troubleshooting
description: Fix common CastMane problems on Wayland and X11.
---

## The app says something is missing

CastMane shows a popup naming the exact package to install. Re-check
[Installation](/getting-started/installation/) for the per-distro commands.

## No screen-share dialog appears (Wayland)

- Make sure `xdg-desktop-portal` is running with a ScreenCast backend
  (KDE and GNOME both provide one).
- On exotic compositors (e.g. minimal wlroots setups), install
  `xdg-desktop-portal-wlr` and configure your compositor's portal line.

## Recording dialog times out

You have 180 seconds to confirm the system screen-share dialog. If it
expires, just press **Record** again.

## The output file is missing

- Finished files are timestamped `castmane_*.mp4` in `~/Videos/CastMane`.
- If the app was killed, look for the `*.mkv.part` (Wayland) or `*.mp4.part`
  (X11) file in the same folder — see
  [Usage](/getting-started/usage/#recovering-an-interrupted-recording).

## Bug reports

Issues and pull requests are welcome at
[akamusti/CastMane](https://github.com/akamusti/CastMane). For lost or corrupt
footage, please include `ffprobe` output and steps to reproduce —
crash-safety is the point of this app.
