"""Entry point for `python -m castmane` / the `castmane` command."""
from __future__ import annotations

import argparse
import sys
import time


def _parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(prog="castmane")
    p.add_argument("--record", action="store_true",
                   help="headless record without GUI (automation)")
    p.add_argument("--duration", type=float, default=0,
                   help="seconds to record with --record (0 = until Ctrl-C)")
    p.add_argument("--replay-save", action="store_true",
                   help="save the replay buffer and exit")
    return p.parse_args(argv)


def _headless_record(duration: float) -> int:
    from .backends import create_backend
    from .config import AppConfig

    cfg = AppConfig.load()
    rec = create_backend(cfg)
    try:
        final = rec.start()
    except Exception as e:  # noqa: BLE001
        print(f"Could not start: {e}", file=sys.stderr)
        return 1
    tmp = rec.state.tmp_path
    print(f"Recording -> {tmp.name if tmp else final.name}")
    try:
        if duration > 0:
            time.sleep(duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    out = rec.stop()
    if out:
        print(f"Saved: {out}")
        return 0
    print(f"Error: {rec.state.last_error}", file=sys.stderr)
    return 1


def _replay_save_cli() -> int:
    from . import replay as replay_mod
    from .config import AppConfig

    cfg = AppConfig.load()
    if not cfg.replay_enabled:
        print("Replay buffer is disabled.", file=sys.stderr)
        return 2
    segs = replay_mod.list_segments(cfg.output_dir)
    picked = replay_mod.select_segments_for_save(segs, cfg.replay_seconds)
    if not picked:
        print("Replay buffer is empty.", file=sys.stderr)
        return 2
    dest = cfg.next_output_path()
    if replay_mod.save_replay(picked, dest):
        print(f"Replay saved: {dest}")
        return 0
    print("Replay save failed.", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.replay_save:
        return _replay_save_cli()
    if args.record:
        return _headless_record(args.duration)
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .app import MainWindow
    from .config import AppConfig
    from .theme import logo_path

    app = QApplication(sys.argv)
    app.setApplicationName("CastMane")
    app.setOrganizationName("CastMane")
    icon = logo_path()
    if icon:
        app.setWindowIcon(QIcon(icon))
    win = MainWindow(AppConfig.load())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
