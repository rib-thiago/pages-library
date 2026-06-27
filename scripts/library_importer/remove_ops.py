from __future__ import annotations

import shutil
from pathlib import Path

from .catalog import file_size, load_catalog, save_catalog, show_catalog_validation
from .config import AppConfig, AUDIO_EXTENSIONS
from .paths import DELETE_REFUSAL_MESSAGE, assert_can_delete_repo_copy, human_size, repo_relative, safe_repo_path, slugify
from .ui import choose_from_list, confirm, panel, print_msg


def album_catalog_files(repo_root: Path, album: dict) -> list[Path]:
    paths = []
    cover = safe_repo_path(repo_root, album.get("cover"))
    if cover:
        paths.append(cover)
    for track in album.get("tracks", []):
        for source in track.get("sources", []):
            path = safe_repo_path(repo_root, source.get("src"))
            if path:
                paths.append(path)
    return paths


def probable_album_dir(repo_root: Path, album: dict, files: list[Path]) -> Path:
    if files:
        parents = {path.parent for path in files}
        if len(parents) == 1:
            return next(iter(parents))
    return repo_root / "music" / slugify(album.get("artist", "")) / slugify(album.get("title", ""))


def choose_pdf(catalog: dict, repo_root: Path):
    return choose_from_list(
        catalog["pdfs"],
        "PDFs cadastrados",
        ["nº", "id", "título", "autor", "arquivo"],
        lambda index, item: [str(index), item.get("id", ""), item.get("title", ""), item.get("author", ""), item.get("file", "")],
    )


def choose_album(catalog: dict):
    return choose_from_list(
        catalog["albums"],
        "Álbuns cadastrados",
        ["nº", "id", "título", "artista", "faixas"],
        lambda index, item: [str(index), item.get("id", ""), item.get("title", ""), item.get("artist", ""), str(len(item.get("tracks", [])))],
    )


def remove_pdf_flow(config: AppConfig) -> dict | None:
    catalog = load_catalog(config.catalog)
    item = choose_pdf(catalog, config.repo_root)
    if not item:
        return None
    copy_path = safe_repo_path(config.repo_root, item.get("file"))
    panel(
        "Resumo da remoção de PDF",
        "\n".join(
            [
                f"id: {item.get('id')}",
                f"título: {item.get('title')}",
                "Arquivo original: em /srv/media, não será tocado",
                f"Cópia publicada: {item.get('file')}",
                f"Existe: {'sim' if copy_path and copy_path.exists() else 'não'}",
                f"Tamanho: {human_size(file_size(copy_path))}",
            ]
        ),
        "yellow",
    )
    panel("Aviso", "A biblioteca original em /srv/media NÃO será apagada.", "yellow")
    print("\n1) Remover apenas do catálogo")
    print("2) Remover do catálogo e apagar a cópia publicada em pdfs/")
    print("0) Cancelar")
    action = input("Escolha: ").strip().lower()
    if action in {"0", "q"}:
        print("Operação cancelada.")
        return None
    if action not in {"1", "2"}:
        print("Opção inválida.")
        return None
    if action == "1" and not confirm("Confirmar remoção apenas do catálogo?", False):
        return None
    if action == "2":
        try:
            delete_path = assert_can_delete_repo_copy(config.repo_root, copy_path, "pdfs")
        except ValueError:
            print_msg(DELETE_REFUSAL_MESSAGE, "red")
            return None
        if not confirm(f"Confirmar apagar apenas a cópia publicada dentro de {config.repo_root}?", False):
            return None
    catalog["pdfs"] = [pdf for pdf in catalog["pdfs"] if pdf.get("id") != item.get("id")]
    if action == "2" and copy_path and copy_path.exists():
        delete_path.unlink()
        parent = delete_path.parent
        if parent.exists() and not any(parent.iterdir()) and confirm(f"A pasta {repo_relative(config.repo_root, parent)} ficou vazia. Remover pasta?", False):
            assert_can_delete_repo_copy(config.repo_root, parent, "pdfs")
            parent.rmdir()
    save_catalog(config.catalog, catalog)
    show_catalog_validation(config.catalog)
    print_msg("PDF removido.", "green")
    return {"kind": "remove-pdf", "id": item.get("id"), "page": "pdf.html"}


def remove_album_flow(config: AppConfig) -> dict | None:
    catalog = load_catalog(config.catalog)
    item = choose_album(catalog)
    if not item:
        return None
    files = album_catalog_files(config.repo_root, item)
    album_dir = probable_album_dir(config.repo_root, item, files)
    track_files = [path for path in files if path.suffix.lower() in AUDIO_EXTENSIONS]
    existing_size = sum(file_size(path) for path in files)
    panel(
        "Resumo da remoção de álbum",
        "\n".join(
            [
                f"id: {item.get('id')}",
                f"artista: {item.get('artist')}",
                f"título: {item.get('title')}",
                "Biblioteca original: /srv/media não será tocada",
                f"Diretório copiado no repo: {repo_relative(config.repo_root, album_dir)}",
                f"Faixas: {len(track_files)}",
                f"Tamanho: {human_size(existing_size)}",
            ]
        ),
        "yellow",
    )
    print("\n1) Remover apenas do catálogo")
    print("2) Remover do catálogo e apagar a cópia publicada em music/")
    print("0) Cancelar")
    action = input("Escolha: ").strip().lower()
    if action in {"0", "q"}:
        print("Operação cancelada.")
        return None
    if action not in {"1", "2"}:
        print("Opção inválida.")
        return None
    if action == "1" and not confirm("Confirmar remoção apenas do catálogo?", False):
        return None
    if action == "2":
        try:
            delete_dir = assert_can_delete_repo_copy(config.repo_root, album_dir, "music")
        except ValueError:
            print_msg(DELETE_REFUSAL_MESSAGE, "red")
            return None
        if input("Digite APAGAR-COPIA para confirmar: ").strip() != "APAGAR-COPIA":
            print("Operação cancelada.")
            return None
    catalog["albums"] = [album for album in catalog["albums"] if album.get("id") != item.get("id")]
    if action == "2" and album_dir.exists():
        shutil.rmtree(delete_dir)
    save_catalog(config.catalog, catalog)
    show_catalog_validation(config.catalog)
    print_msg("Álbum removido.", "green")
    return {"kind": "remove-album", "id": item.get("id"), "page": "album.html"}

