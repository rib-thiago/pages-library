from __future__ import annotations

import re
from pathlib import Path

from .config import AUDIO_EXTENSIONS, COVER_NAMES, MAX_RESULTS
from .paths import is_hidden_path, natural_sort_key, relative_display, slugify


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value.replace("_", " ")).strip()
    value = re.sub(r"\s+-\s+[^-]+$", "", value).strip()
    return value


def infer_year(value: str) -> str:
    match = re.search(r"(?:^|[^\d])((?:19|20)\d{2})(?:[^\d]|$)", value)
    return match.group(1) if match else ""


def direct_audio_files(directory: Path) -> list[Path]:
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS],
        key=natural_sort_key,
    )


def search_pdfs(calibre_root: Path, term: str) -> list[Path]:
    needle = term.casefold()
    results = []
    if not calibre_root.exists():
        return results
    for path in calibre_root.rglob("*.pdf"):
        if is_hidden_path(path, calibre_root):
            continue
        if needle in str(path).casefold():
            results.append(path)
            if len(results) >= MAX_RESULTS:
                break
    return sorted(results, key=natural_sort_key)


def search_album_dirs(music_root: Path, term: str) -> list[tuple[Path, list[Path], int]]:
    needle = term.casefold()
    results = []
    if not music_root.exists():
        return results
    for directory in music_root.rglob("*"):
        if is_hidden_path(directory, music_root) or not directory.is_dir():
            continue
        if needle not in str(directory).casefold():
            continue
        tracks = direct_audio_files(directory)
        if not tracks:
            continue
        total_size = sum(track.stat().st_size for track in tracks)
        results.append((directory, tracks, total_size))
        if len(results) >= MAX_RESULTS:
            break
    return sorted(results, key=lambda item: natural_sort_key(item[0]))


def list_top_level_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir() and not is_hidden_path(path, root)], key=natural_sort_key)


def infer_pdf_metadata(pdf_path: Path, calibre_root: Path) -> dict:
    title = clean_title(pdf_path.stem)
    author = ""
    try:
        parts = pdf_path.relative_to(calibre_root).parts
        if len(parts) >= 3:
            author = parts[0]
            title = clean_title(Path(parts[1]).name)
    except ValueError:
        author = pdf_path.parent.parent.name if pdf_path.parent.parent != pdf_path.parent else ""
        title = clean_title(pdf_path.parent.name or pdf_path.stem)
    year = infer_year(title) or infer_year(pdf_path.name)
    title = re.sub(r"\s*\((19|20)\d{2}\)\s*", " ", title).strip() or title
    return {
        "id": slugify(" ".join(part for part in [author, title] if part)),
        "title": title,
        "author": author,
        "year": year,
        "collection": "Biblioteca Calibre",
        "tags": [],
        "description": "PDF selecionado da biblioteca Calibre.",
    }


def infer_album_metadata(album_dir: Path, music_root: Path) -> dict:
    artist = ""
    collection = "Música"
    try:
        parts = album_dir.relative_to(music_root).parts
        if parts:
            artist = parts[0]
        if len(parts) > 2:
            collection = parts[-2]
    except ValueError:
        pass
    title = clean_title(album_dir.name)
    year = infer_year(album_dir.name)
    title = re.sub(r"\s*\((19|20)\d{2}\)\s*", " ", title).strip()
    title = re.sub(r"^(19|20)\d{2}\s*[-_. ]+", "", title).strip() or album_dir.name
    return {
        "id": slugify(" ".join(part for part in [artist, title, year] if part)),
        "artist": artist,
        "title": title,
        "year": year,
        "collection": collection,
        "tags": [],
        "description": "Álbum selecionado da biblioteca musical.",
    }


def find_cover(album_dir: Path) -> Path | None:
    lower_map = {path.name.lower(): path for path in album_dir.iterdir() if path.is_file()}
    for name in COVER_NAMES:
        if name in lower_map:
            return lower_map[name]
    return None


def browse_label(root: Path, path: Path) -> str:
    return relative_display(root, path)

