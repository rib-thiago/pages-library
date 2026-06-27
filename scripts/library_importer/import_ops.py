from __future__ import annotations

import json
import shutil
from pathlib import Path

from .catalog import catalog_id_exists, load_catalog, save_catalog
from .config import AppConfig, GITHUB_PAGES_BASE, MIME_TYPES
from .media_scan import direct_audio_files, find_cover, infer_album_metadata, infer_pdf_metadata
from .paths import human_size, natural_sort_key, repo_relative, slugify
from .ui import confirm, panel, parse_tags, print_msg, prompt_with_default


def copy_file(source: Path, destination: Path, description: str) -> None:
    from .ui import HAS_RICH, console

    if HAS_RICH:
        with console.status(description):
            shutil.copy2(source, destination)
    else:
        print(description)
        shutil.copy2(source, destination)


def print_urls(page: str, item_id: str) -> None:
    print(f"URL local: {page}?id={item_id}")
    print(f"URL GitHub Pages: {GITHUB_PAGES_BASE}/{page}?id={item_id}")


def print_size_alerts(files: list[Path], total_size: int) -> None:
    messages = []
    for path in files:
        size = path.stat().st_size
        if size > 100 * 1024 * 1024:
            messages.append(f"{path.name}: GitHub normalmente bloqueia arquivo individual acima de 100 MiB ({human_size(size)}).")
        elif size > 50 * 1024 * 1024:
            messages.append(f"{path.name}: GitHub pode emitir warning para arquivo acima de 50 MiB ({human_size(size)}).")
        elif size > 25 * 1024 * 1024:
            messages.append(f"{path.name}: aviso conservador: arquivo grande para Git/GitHub Pages ({human_size(size)}).")
    if total_size > 1024 * 1024 * 1024:
        messages.append("Total acima de 1 GiB: não recomendado para GitHub Pages.")
    elif total_size > 200 * 1024 * 1024:
        messages.append("Total acima de 200 MiB: repositório ficará pesado.")
    if messages:
        panel("Alertas de tamanho", "\n".join(messages), "yellow")


def prompt_action() -> str:
    print("\nAplicar operação?")
    print("1) Copiar arquivos e atualizar catálogo")
    print("2) Dry-run: mostrar o que faria")
    print("0) Cancelar")
    while True:
        answer = input("Escolha: ").strip().lower()
        if answer in {"0", "q"}:
            return "0"
        if answer in {"1", "2"}:
            return answer
        print("Opção inválida.")


def import_pdf(config: AppConfig, source: Path) -> dict | None:
    meta = infer_pdf_metadata(source, config.calibre_root)
    print("\nRevise os metadados:")
    item_id = slugify(prompt_with_default("id", meta["id"]))
    title = prompt_with_default("title", meta["title"])
    author = prompt_with_default("author", meta["author"])
    year = prompt_with_default("year", meta["year"])
    collection = prompt_with_default("collection", meta["collection"])
    tags = parse_tags(prompt_with_default("tags separados por vírgula", ", ".join(meta["tags"])))
    description = prompt_with_default("description", meta["description"])

    catalog = load_catalog(config.catalog)
    if catalog_id_exists(catalog, item_id):
        print("Operação recusada: id já existe no catálogo.")
        return None
    destination = config.repo_root / "pdfs" / slugify(author or "autor-desconhecido") / f"{slugify(title or source.stem)}.pdf"
    if destination.exists() and not confirm(f"A cópia publicada já existe: {destination}. Sobrescrever?", False):
        return None
    item = {
        "id": item_id,
        "title": title,
        "author": author,
        "year": year,
        "collection": collection,
        "tags": tags,
        "description": description,
        "file": repo_relative(config.repo_root, destination),
    }
    panel("Resumo da importação do PDF", f"Origem: {source}\nCópia publicada: {destination}\nEntrada:\n{json.dumps(item, ensure_ascii=False, indent=2)}", "cyan")
    print_size_alerts([source], source.stat().st_size)
    action = prompt_action()
    if action == "0":
        print("Operação cancelada.")
        return None
    if action == "2":
        print("Dry-run concluído. Nada foi alterado.")
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy_file(source, destination, "Copiando PDF")
    catalog["pdfs"].append(item)
    save_catalog(config.catalog, catalog)
    print_msg("PDF importado com sucesso.", "green")
    print_urls("pdf.html", item_id)
    return {"kind": "pdf", "id": item_id, "page": "pdf.html"}


def build_track_entries(repo_root: Path, destination_dir: Path, tracks: list[Path]) -> list[dict]:
    entries = []
    used_names = set()
    for index, source in enumerate(tracks, start=1):
        title = source.stem
        title = title.split(" - ", 1)[1] if " - " in title and title[:2].isdigit() else title
        extension = source.suffix.lower()
        filename = f"{index:02d}-{slugify(title)}{extension}"
        while filename in used_names:
            filename = f"{index:02d}-{slugify(title)}-{len(used_names)}{extension}"
        used_names.add(filename)
        destination = destination_dir / filename
        entries.append({"number": index, "title": title, "sources": [{"src": repo_relative(repo_root, destination), "type": MIME_TYPES[extension]}]})
    return entries


def import_album(config: AppConfig, album_dir: Path, tracks: list[Path] | None = None) -> dict | None:
    tracks = tracks or direct_audio_files(album_dir)
    if not tracks:
        print("Nenhum arquivo de áudio encontrado.")
        return None
    total_size = sum(track.stat().st_size for track in tracks)
    cover = find_cover(album_dir)
    meta = infer_album_metadata(album_dir, config.music_root)
    print("\nRevise os metadados:")
    item_id = slugify(prompt_with_default("id", meta["id"]))
    artist = prompt_with_default("artist", meta["artist"])
    title = prompt_with_default("title", meta["title"])
    year = prompt_with_default("year", meta["year"])
    collection = prompt_with_default("collection", meta["collection"])
    tags = parse_tags(prompt_with_default("tags separados por vírgula", ", ".join(meta["tags"])))
    description = prompt_with_default("description", meta["description"])

    catalog = load_catalog(config.catalog)
    if catalog_id_exists(catalog, item_id):
        print("Operação recusada: id já existe no catálogo.")
        return None
    destination_dir = config.repo_root / "music" / slugify(artist or "artista-desconhecido") / slugify(title or album_dir.name)
    if destination_dir.exists() and not confirm(f"A cópia publicada já existe: {destination_dir}. Sobrescrever?", False):
        return None
    copied_tracks = build_track_entries(config.repo_root, destination_dir, tracks)
    item = {
        "id": item_id,
        "artist": artist,
        "title": title,
        "year": year,
        "collection": collection,
        "tags": tags,
        "description": description,
        "tracks": copied_tracks,
    }
    if cover:
        item["cover"] = repo_relative(config.repo_root, destination_dir / f"cover{cover.suffix.lower()}")
    panel("Resumo da importação do álbum", f"Origem: {album_dir}\nCópia publicada: {destination_dir}\nFaixas: {len(tracks)}\nTamanho: {human_size(total_size)}", "cyan")
    print_size_alerts(tracks, total_size)
    action = prompt_action()
    if action == "0":
        print("Operação cancelada.")
        return None
    if action == "2":
        print("Dry-run concluído. Nada foi alterado.")
        return None
    if destination_dir.exists():
        from .paths import assert_can_delete_repo_copy

        assert_can_delete_repo_copy(config.repo_root, destination_dir, "music")
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source, track in zip(tracks, copied_tracks):
        copy_file(source, config.repo_root / track["sources"][0]["src"], f"Copiando {source.name}")
    if cover:
        copy_file(cover, config.repo_root / item["cover"], "Copiando capa")
    catalog["albums"].append(item)
    save_catalog(config.catalog, catalog)
    print_msg("Álbum importado com sucesso.", "green")
    print_urls("album.html", item_id)
    return {"kind": "album", "id": item_id, "page": "album.html"}

