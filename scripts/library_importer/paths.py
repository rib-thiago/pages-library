from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import FORBIDDEN_SOURCE_ROOTS


DELETE_REFUSAL_MESSAGE = (
    "Operação recusada: o script nunca apaga arquivos da biblioteca original; "
    "somente cópias dentro do repo pages-library."
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value)
    ascii_value = re.sub(r"-+", "-", ascii_value)
    return ascii_value.strip("-") or "item"


def natural_sort_key(value: str | Path) -> list:
    text = str(value.name if isinstance(value, Path) else value)
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def human_size(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{size} B"


def repo_relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def relative_display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def is_hidden_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part.startswith(".") for part in parts)


def safe_repo_path(repo_root: Path, relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (repo_root / candidate).resolve()
    return resolved if is_inside_repo(repo_root, resolved) else None


def is_inside_repo(repo_root: Path, path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    return True


def is_inside_repo_music(repo_root: Path, path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to((repo_root / "music").resolve())
    except ValueError:
        return False
    return True


def is_inside_repo_pdfs(repo_root: Path, path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to((repo_root / "pdfs").resolve())
    except ValueError:
        return False
    return True


def is_forbidden_source_path(path: Path | None) -> bool:
    if path is None:
        return True
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in FORBIDDEN_SOURCE_ROOTS)


def assert_can_delete_repo_copy(repo_root: Path, path: Path | None, expected_area: str) -> Path:
    if path is None or ".." in path.parts:
        raise ValueError(DELETE_REFUSAL_MESSAGE)
    resolved = path.resolve()
    if is_forbidden_source_path(resolved) or not is_inside_repo(repo_root, resolved):
        raise ValueError(DELETE_REFUSAL_MESSAGE)
    if expected_area == "pdfs" and not is_inside_repo_pdfs(repo_root, resolved):
        raise ValueError(DELETE_REFUSAL_MESSAGE)
    if expected_area == "music" and not is_inside_repo_music(repo_root, resolved):
        raise ValueError(DELETE_REFUSAL_MESSAGE)
    return resolved

