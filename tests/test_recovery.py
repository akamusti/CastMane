"""Leftover `.part` recovery: find, restore, discard."""
from pathlib import Path

from castmane.i18n import STRINGS
from castmane.recorder import (
    final_name_for_part,
    find_stale_parts,
    recover_part,
)


def test_recovery_strings_translated():
    for key in (
        "recovery_title", "recovery_text", "recovery_restore",
        "recovery_discard", "recovery_later", "recovery_restored",
        "recovery_deleted", "recovery_failed",
    ):
        assert STRINGS["en"].get(key), f"{key} missing in en"
        assert STRINGS["tr"].get(key), f"{key} missing in tr"


def test_find_stale_parts(tmp_path):
    assert find_stale_parts(tmp_path / "missing-dir") == []
    (tmp_path / "take.mp4").write_bytes(b"x")
    good = tmp_path / "take_2026-01-01_00-00-00.mp4.part"
    good.write_bytes(b"data" * 100)
    empty = tmp_path / "empty.mkv.part"
    empty.write_bytes(b"")
    found = find_stale_parts(tmp_path)
    assert good in found
    assert empty in found
    assert tmp_path / "take.mp4" not in found


def test_final_name_strips_part():
    assert final_name_for_part(Path("a.mp4.part")).name == "a.mp4"
    assert final_name_for_part(Path("b.mkv.part")).name == "b.mkv"


def test_recover_part_promotes_nonempty(tmp_path):
    tmp = tmp_path / "take.mp4.part"
    tmp.write_bytes(b"data" * 100)
    done = recover_part(tmp)
    assert done is not None and done.name == "take.mp4"
    assert done.exists() and not tmp.exists()


def test_recover_part_keeps_empty(tmp_path):
    tmp = tmp_path / "empty.mp4.part"
    tmp.write_bytes(b"")
    assert recover_part(tmp) is None
    assert tmp.exists()  # crash residue is never auto-deleted
