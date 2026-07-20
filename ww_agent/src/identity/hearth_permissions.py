# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner-only filesystem permissions for one resident hearth."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat


class HearthPermissionError(RuntimeError):
    """Raised when a resident hearth cannot be secured without leaving its root."""


@dataclass(frozen=True)
class HearthPermissionReport:
    directories_checked: int = 0
    directories_changed: int = 0
    files_checked: int = 0
    files_changed: int = 0
    symlinks_skipped: int = 0
    special_entries_skipped: int = 0


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def _set_mode(path: Path, expected: int) -> bool:
    if _mode(path) == expected:
        return False
    try:
        os.chmod(path, expected, follow_symlinks=False)
    except OSError as exc:
        raise HearthPermissionError(
            f"Could not secure hearth path {path}: {exc}"
        ) from exc
    return True


def secure_hearth_permissions(root: Path) -> HearthPermissionReport:
    """Make one hearth owner-only without following links outside it.

    Directories become ``0700`` and regular files become ``0600``. Symbolic links and
    special filesystem entries are left untouched. A symlink cannot be used as the
    hearth root.
    """

    root = Path(root)
    if root.is_symlink():
        raise HearthPermissionError(f"Hearth root must not be a symbolic link: {root}")
    if not root.is_dir():
        raise HearthPermissionError(f"Hearth root is not a directory: {root}")

    directories_checked = 1
    directories_changed = int(_set_mode(root, 0o700))
    files_checked = 0
    files_changed = 0
    symlinks_skipped = 0
    special_entries_skipped = 0

    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        retained_directories: list[str] = []
        for name in directory_names:
            path = current_path / name
            if path.is_symlink():
                symlinks_skipped += 1
                continue
            try:
                entry_mode = path.lstat().st_mode
            except OSError as exc:
                raise HearthPermissionError(
                    f"Could not inspect hearth path {path}: {exc}"
                ) from exc
            if not stat.S_ISDIR(entry_mode):
                special_entries_skipped += 1
                continue
            directories_checked += 1
            directories_changed += int(_set_mode(path, 0o700))
            retained_directories.append(name)
        directory_names[:] = retained_directories

        for name in file_names:
            path = current_path / name
            if path.is_symlink():
                symlinks_skipped += 1
                continue
            try:
                entry_mode = path.lstat().st_mode
            except OSError as exc:
                raise HearthPermissionError(
                    f"Could not inspect hearth path {path}: {exc}"
                ) from exc
            if not stat.S_ISREG(entry_mode):
                special_entries_skipped += 1
                continue
            files_checked += 1
            files_changed += int(_set_mode(path, 0o600))

    return HearthPermissionReport(
        directories_checked=directories_checked,
        directories_changed=directories_changed,
        files_checked=files_checked,
        files_changed=files_changed,
        symlinks_skipped=symlinks_skipped,
        special_entries_skipped=special_entries_skipped,
    )
