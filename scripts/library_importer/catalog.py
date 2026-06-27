from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .paths import human_size, safe_repo_path
from .ui import panel, table, truncate_text


def load_catalog(catalog_path: Path) -> dict:
    with catalog_path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)
    catalog.setdefault("pdfs", [])
    catalog.setdefault("albums", [])
    return catalog


def backup_catalog(catalog_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = catalog_path.with_name(f"{catalog_path.name}.bak-{timestamp}")
    shutil.copy2(catalog_path, backup_path)
    return backup_path


def save_catalog(catalog_path: Path, catalog: dict) -> None:
    backup_catalog(catalog_path)
    with catalog_path.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, indent=2, ensure_ascii=False)
        file.write("\n")
    load_catalog(catalog_path)


def validate_catalog(catalog_path: Path) -> dict:
    catalog = load_catalog(catalog_path)
    json.dumps(catalog, ensure_ascii=False, indent=2)
    return catalog


def catalog_id_exists(catalog: dict, item_id: str) -> bool:
    return any(item.get("id") == item_id for item in catalog.get("pdfs", [])) or any(
        item.get("id") == item_id for item in catalog.get("albums", [])
    )


def file_size(path: Path | None) -> int:
    return path.stat().st_size if path and path.exists() and path.is_file() else 0


def show_catalog_validation(catalog_path: Path) -> None:
    catalog = validate_catalog(catalog_path)
    panel("Catálogo válido", f"Arquivo: {catalog_path}\nPDFs: {len(catalog['pdfs'])}\nÁlbuns: {len(catalog['albums'])}", "green")


def list_catalog_pdfs(catalog_path: Path, repo_root: Path) -> None:
    catalog = load_catalog(catalog_path)
    rows = []
    for index, item in enumerate(catalog["pdfs"], start=1):
        path = safe_repo_path(repo_root, item.get("file"))
        rows.append(
            [
                str(index),
                truncate_text(item.get("id"), 30),
                truncate_text(item.get("title"), 30),
                truncate_text(item.get("author"), 24),
                str(item.get("year", "")),
                "sim" if path and path.exists() else "não",
                human_size(file_size(path)),
            ]
        )
    table("PDFs cadastrados", ["nº", "id", "título", "autor", "ano", "existe?", "tamanho"], rows)


def list_catalog_albums(catalog_path: Path, repo_root: Path) -> None:
    catalog = load_catalog(catalog_path)
    rows = []
    for index, item in enumerate(catalog["albums"], start=1):
        tracks = item.get("tracks", [])
        rows.append(
            [
                str(index),
                truncate_text(item.get("id"), 30),
                truncate_text(item.get("title"), 30),
                truncate_text(item.get("artist"), 24),
                str(item.get("year", "")),
                str(len(tracks)),
            ]
        )
    table("Álbuns cadastrados", ["nº", "id", "título", "artista", "ano", "faixas"], rows)

