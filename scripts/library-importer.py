#!/usr/bin/env python3
"""Interactive importer for the static Pages Library catalog."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import signal
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


DEFAULT_CALIBRE_ROOT = Path("/srv/media/calibre-library")
DEFAULT_MUSIC_ROOT = Path("/srv/media/music")
GITHUB_PAGES_BASE = "https://rib-thiago.github.io/pages-library"
MAX_RESULTS = 30
PAGE_SIZE = 100
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav"}
MIME_TYPES = {
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
}
COVER_NAMES = [
    "cover.jpg",
    "cover.jpeg",
    "folder.jpg",
    "folder.jpeg",
    "front.jpg",
    "front.jpeg",
    "cover.png",
    "folder.png",
    "front.png",
]


def handle_sigint(signum, frame) -> None:
    print("\nInterrompido pelo usuário.")
    raise SystemExit(0)


def load_catalog(catalog_path: Path) -> dict:
    with catalog_path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    catalog.setdefault("pdfs", [])
    catalog.setdefault("albums", [])
    return catalog


def save_catalog(catalog_path: Path, catalog: dict) -> None:
    backup_catalog(catalog_path)
    with catalog_path.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, indent=2, ensure_ascii=False)
        file.write("\n")

    load_catalog(catalog_path)


def backup_catalog(catalog_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = catalog_path.with_name(f"{catalog_path.name}.bak-{timestamp}")
    shutil.copy2(catalog_path, backup_path)
    return backup_path


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower()
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


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def confirm(message: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(message + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "s", "sim"}


def prompt_with_default(label: str, default: str = "") -> str:
    if default:
        answer = input(f"{label} [{default}]: ").strip()
        return answer or default
    return input(f"{label}: ").strip()


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


def list_top_level_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir() and not is_hidden_path(path, root)], key=natural_sort_key)


def is_hidden_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part.startswith(".") for part in parts)


def direct_audio_files(directory: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        ],
        key=natural_sort_key,
    )


def search_album_dirs(music_root: Path, term: str) -> list[tuple[Path, list[Path], int]]:
    needle = term.casefold()
    results = []
    if not music_root.exists():
        return results

    for directory in music_root.rglob("*"):
        if is_hidden_path(directory, music_root):
            continue
        if not directory.is_dir() or needle not in str(directory).casefold():
            continue

        tracks = direct_audio_files(directory)
        if not tracks:
            continue

        total_size = sum(track.stat().st_size for track in tracks)
        results.append((directory, tracks, total_size))
        if len(results) >= MAX_RESULTS:
            break

    return sorted(results, key=lambda item: natural_sort_key(item[0]))


def infer_pdf_metadata(pdf_path: Path, calibre_root: Path) -> dict:
    title = clean_title(pdf_path.stem)
    author = ""

    try:
        relative = pdf_path.relative_to(calibre_root)
        parts = relative.parts
        if len(parts) >= 3:
            author = parts[0]
            title = clean_title(Path(parts[1]).name)
    except ValueError:
        if pdf_path.parent.parent != pdf_path.parent:
            author = pdf_path.parent.parent.name
        title = clean_title(pdf_path.parent.name or pdf_path.stem)

    year = infer_year(title) or infer_year(pdf_path.name)
    clean_title_without_year = re.sub(r"\s*\((19|20)\d{2}\)\s*", " ", title).strip()
    return {
        "id": slugify(" ".join(part for part in [author, clean_title_without_year] if part)),
        "title": clean_title_without_year or title,
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
        relative = album_dir.relative_to(music_root)
        parts = relative.parts
        if parts:
            artist = parts[0]
        if len(parts) > 2:
            collection = parts[-2]
    except ValueError:
        pass

    title = clean_title(album_dir.name)
    year = infer_year(album_dir.name)
    title_without_year = re.sub(r"\s*\((19|20)\d{2}\)\s*", " ", title).strip()
    title_without_year = re.sub(r"^(19|20)\d{2}\s*[-_. ]+", "", title_without_year).strip()

    return {
        "id": slugify(" ".join(part for part in [artist, title_without_year, year] if part)),
        "artist": artist,
        "title": title_without_year or title,
        "year": year,
        "collection": collection,
        "tags": [],
        "description": "Álbum selecionado da biblioteca musical.",
    }


def infer_year(value: str) -> str:
    match = re.search(r"(?:^|[^\d])((?:19|20)\d{2})(?:[^\d]|$)", value)
    return match.group(1) if match else ""


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value.replace("_", " ")).strip()
    value = re.sub(r"\s+-\s+[^-]+$", "", value).strip()
    return value


def choose_result(results: list, formatter) -> object | None:
    if not results:
        print("Nenhum resultado encontrado.")
        return None

    for index, result in enumerate(results, start=1):
        print(f"{index}) {formatter(result)}")

    while True:
        answer = input("Escolha um número ou 0 para cancelar: ").strip().lower()
        if answer in {"0", "q"}:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(results):
            return results[int(answer) - 1]
        print("Opção inválida.")


def choose_from_list(items: list, formatter, title: str = "Escolha") -> object | None:
    return paginate_choices(items, formatter, title)


def paginate_choices(items: list, formatter, title: str = "Escolha", page_size: int = PAGE_SIZE) -> object | None:
    if not items:
        print("Nenhuma entrada encontrada.")
        return None

    page = 0
    total_pages = (len(items) + page_size - 1) // page_size
    while True:
        start = page * page_size
        page_items = items[start : start + page_size]
        print(f"\n{title}")
        print(f"Página {page + 1}/{total_pages}")
        for index, item in enumerate(page_items, start=1):
            print(f"{index}) {formatter(item)}")
        print("n = próxima, p = anterior, 0 = voltar")

        answer = input("Escolha: ").strip().lower()
        if answer in {"0", "q"}:
            return None
        if answer == "n":
            if page + 1 < total_pages:
                page += 1
            else:
                print("Você já está na última página.")
            continue
        if answer == "p":
            if page > 0:
                page -= 1
            else:
                print("Você já está na primeira página.")
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(page_items):
            return page_items[int(answer) - 1]
        print("Opção inválida. Digite um número, n, p, 0 ou q.")


def catalog_id_exists(catalog: dict, item_id: str) -> bool:
    return any(item.get("id") == item_id for item in catalog.get("pdfs", [])) or any(
        item.get("id") == item_id for item in catalog.get("albums", [])
    )


def repo_relative(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def relative_display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def prompt_action() -> str:
    print("\nAplicar operação?")
    print("1) Copiar arquivos e atualizar catálogo")
    print("2) Dry-run: mostrar o que faria")
    print("0) Cancelar")
    while True:
        answer = input("Escolha: ").strip().lower()
        if answer in {"q", "0"}:
            return "0"
        if answer in {"1", "2"}:
            return answer
        print("Opção inválida.")


def add_pdf_flow(args: argparse.Namespace) -> dict | None:
    term = input("Termo de busca para PDF: ").strip()
    if not term:
        print("Busca cancelada.")
        return None

    results = search_pdfs(args.calibre_root, term)
    chosen = choose_result(results, lambda path: relative_display(args.calibre_root, path))
    if not chosen:
        return None

    return import_pdf_path(args, chosen)


def import_pdf_path(args: argparse.Namespace, chosen: Path) -> dict | None:
    if not chosen.exists():
        print("PDF não encontrado.")
        return None

    metadata = infer_pdf_metadata(chosen, args.calibre_root)
    print("\nRevise os metadados:")
    item_id = slugify(prompt_with_default("id", metadata["id"]))
    title = prompt_with_default("title", metadata["title"])
    author = prompt_with_default("author", metadata["author"])
    year = prompt_with_default("year", metadata["year"])
    collection = prompt_with_default("collection", metadata["collection"])
    tags = parse_tags(prompt_with_default("tags separados por vírgula", ", ".join(metadata["tags"])))
    description = prompt_with_default("description", metadata["description"])

    catalog = load_catalog(args.catalog)
    if catalog_id_exists(catalog, item_id):
        print(f"Operação recusada: o id '{item_id}' já existe no catálogo.")
        return None

    author_slug = slugify(author or "autor-desconhecido")
    title_slug = slugify(title or chosen.stem)
    destination_dir = args.repo_root / "pdfs" / author_slug
    destination_file = destination_dir / f"{title_slug}.pdf"

    overwrite = False
    if destination_file.exists():
        overwrite = confirm(f"O arquivo de destino já existe: {destination_file}. Sobrescrever explicitamente?", False)
        if not overwrite:
            print("Operação cancelada.")
            return None

    item = {
        "id": item_id,
        "title": title,
        "author": author,
        "year": year,
        "collection": collection,
        "tags": tags,
        "description": description,
        "file": repo_relative(args.repo_root, destination_file),
    }

    print_pdf_summary(chosen, destination_file, item)
    action = prompt_action()
    if action == "0":
        print("Operação cancelada.")
        return None
    if action == "2":
        print("Dry-run concluído. Nenhum arquivo foi copiado e o catálogo não foi alterado.")
        return None

    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen, destination_file)
    catalog["pdfs"].append(item)
    save_catalog(args.catalog, catalog)
    print("PDF importado com sucesso.")
    print_urls("pdf.html", item_id)
    context = {"kind": "pdf", "id": item_id, "page": "pdf.html"}
    if post_change_menu(args, context) == "exit":
        raise SystemExit(0)
    return context


def print_pdf_summary(source: Path, destination: Path, item: dict) -> None:
    print("\nResumo da importação do PDF")
    print(f"Origem: {source}")
    print(f"Destino: {destination}")
    print(f"Tamanho: {human_size(source.stat().st_size)}")
    print(f"Entrada: {json.dumps(item, ensure_ascii=False, indent=2)}")
    print_urls("pdf.html", item["id"])


def add_album_flow(args: argparse.Namespace) -> dict | None:
    term = input("Termo de busca para álbum: ").strip()
    if not term:
        print("Busca cancelada.")
        return None

    results = search_album_dirs(args.music_root, term)
    chosen = choose_result(
        results,
        lambda item: f"{relative_display(args.music_root, item[0])} | {len(item[1])} faixas | {human_size(item[2])}",
    )
    if not chosen:
        return None

    album_dir, tracks, total_size = chosen
    return import_album_dir(args, album_dir, tracks, total_size)


def import_album_dir(
    args: argparse.Namespace, album_dir: Path, tracks: list[Path] | None = None, total_size: int | None = None
) -> dict | None:
    tracks = tracks if tracks is not None else direct_audio_files(album_dir)
    total_size = total_size if total_size is not None else sum(track.stat().st_size for track in tracks)
    if not tracks:
        print("Nenhum arquivo de áudio encontrado no nível direto desta pasta.")
        return None

    cover = find_cover(album_dir)
    metadata = infer_album_metadata(album_dir, args.music_root)

    print("\nRevise os metadados:")
    item_id = slugify(prompt_with_default("id", metadata["id"]))
    artist = prompt_with_default("artist", metadata["artist"])
    title = prompt_with_default("title", metadata["title"])
    year = prompt_with_default("year", metadata["year"])
    collection = prompt_with_default("collection", metadata["collection"])
    tags = parse_tags(prompt_with_default("tags separados por vírgula", ", ".join(metadata["tags"])))
    description = prompt_with_default("description", metadata["description"])

    catalog = load_catalog(args.catalog)
    if catalog_id_exists(catalog, item_id):
        print(f"Operação recusada: o id '{item_id}' já existe no catálogo.")
        return None

    destination_dir = args.repo_root / "music" / slugify(artist or "artista-desconhecido") / slugify(title or album_dir.name)
    overwrite = False
    if destination_dir.exists():
        overwrite = confirm(f"O diretório de destino já existe: {destination_dir}. Sobrescrever explicitamente?", False)
        if not overwrite:
            print("Operação cancelada.")
            return None

    copied_tracks = build_track_entries(args.repo_root, destination_dir, tracks)
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
        cover_destination = destination_dir / f"cover{cover.suffix.lower()}"
        item["cover"] = repo_relative(args.repo_root, cover_destination)

    print_album_summary(album_dir, destination_dir, tracks, total_size, cover, item)
    action = prompt_action()
    if action == "0":
        print("Operação cancelada.")
        return None
    if action == "2":
        print("Dry-run concluído. Nenhum arquivo foi copiado e o catálogo não foi alterado.")
        return None

    if destination_dir.exists() and overwrite:
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source, track in zip(tracks, copied_tracks):
        destination = args.repo_root / track["sources"][0]["src"]
        shutil.copy2(source, destination)
    if cover:
        shutil.copy2(cover, args.repo_root / item["cover"])

    catalog["albums"].append(item)
    save_catalog(args.catalog, catalog)
    print("Álbum importado com sucesso.")
    print_urls("album.html", item_id)
    context = {"kind": "album", "id": item_id, "page": "album.html"}
    if post_change_menu(args, context) == "exit":
        raise SystemExit(0)
    return context


def find_cover(album_dir: Path) -> Path | None:
    lower_map = {path.name.lower(): path for path in album_dir.iterdir() if path.is_file()}
    for name in COVER_NAMES:
        if name in lower_map:
            return lower_map[name]
    return None


def build_track_entries(repo_root: Path, destination_dir: Path, tracks: list[Path]) -> list[dict]:
    entries = []
    used_names = set()
    for index, source in enumerate(tracks, start=1):
        title = derive_track_title(source)
        extension = source.suffix.lower()
        filename = f"{index:02d}-{slugify(title)}{extension}"
        while filename in used_names:
            filename = f"{index:02d}-{slugify(title)}-{len(used_names)}{extension}"
        used_names.add(filename)
        destination = destination_dir / filename
        entries.append(
            {
                "number": index,
                "title": title,
                "sources": [
                    {
                        "src": repo_relative(repo_root, destination),
                        "type": MIME_TYPES[extension],
                    }
                ],
            }
        )
    return entries


def derive_track_title(path: Path) -> str:
    stem = clean_title(path.stem)
    stem = re.sub(r"^\s*\d+\s*[-_. ]+", "", stem).strip()
    return stem or path.stem


def print_album_summary(
    album_dir: Path,
    destination_dir: Path,
    tracks: list[Path],
    total_size: int,
    cover: Path | None,
    item: dict,
) -> None:
    print("\nResumo da importação do álbum")
    print(f"Origem: {album_dir}")
    print(f"Destino: {destination_dir}")
    print(f"Capa principal: {cover if cover else 'nenhuma'}")
    print(f"Faixas: {len(tracks)}")
    print(f"Tamanho total de áudio: {human_size(total_size)}")

    large_files = [track for track in tracks if track.stat().st_size > 50 * 1024 * 1024]
    if large_files:
        print("Alerta: arquivos individuais acima de 50 MiB:")
        for track in large_files:
            print(f"- {track.name}: {human_size(track.stat().st_size)}")
    if total_size > 1024 * 1024 * 1024:
        print("Alerta: total acima de 1 GiB. Isso é muito grande para GitHub Pages/Git.")
    elif total_size > 200 * 1024 * 1024:
        print("Alerta: total acima de 200 MiB. Isso pode deixar o repositório pesado.")

    print("\nFaixas que serão copiadas:")
    for track in tracks:
        print(f"- {track.name} ({human_size(track.stat().st_size)})")

    print(f"\nEntrada: {json.dumps(item, ensure_ascii=False, indent=2)}")
    print_urls("album.html", item["id"])


def print_urls(page: str, item_id: str) -> None:
    print(f"URL local: {page}?id={item_id}")
    print(f"URL GitHub Pages: {GITHUB_PAGES_BASE}/{page}?id={item_id}")


def list_catalog_pdfs(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    pdfs = catalog.get("pdfs", [])
    if not pdfs:
        print("Nenhum PDF cadastrado.")
        return
    for item in pdfs:
        print(f"- {item.get('id')} | {item.get('author')} | {item.get('title')} | {item.get('file')}")


def list_catalog_albums(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    albums = catalog.get("albums", [])
    if not albums:
        print("Nenhum álbum cadastrado.")
        return
    for item in albums:
        tracks = len(item.get("tracks", []))
        print(f"- {item.get('id')} | {item.get('artist')} | {item.get('title')} | {tracks} faixas")


def validate_catalog(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    json.dumps(catalog, ensure_ascii=False, indent=2)
    print(f"Catálogo válido: {args.catalog}")
    print(f"PDFs: {len(catalog.get('pdfs', []))}")
    print(f"Álbuns: {len(catalog.get('albums', []))}")


def safe_repo_path(repo_root: Path, relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    return resolved


def safe_music_dir(repo_root: Path, directory: Path | None) -> Path | None:
    if directory is None:
        return None
    resolved = directory.resolve()
    music_root = (repo_root / "music").resolve()
    try:
        resolved.relative_to(music_root)
    except ValueError:
        return None
    return resolved


def file_size(path: Path | None) -> int:
    return path.stat().st_size if path and path.exists() and path.is_file() else 0


def remove_item_submenu(args: argparse.Namespace) -> None:
    while True:
        print("\nRemover item\n")
        print("1) Remover PDF")
        print("2) Remover álbum")
        print("0) Voltar")
        choice = input("Escolha: ").strip().lower()

        if choice == "1":
            remove_pdf_flow(args)
        elif choice == "2":
            remove_album_flow(args)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")


def remove_pdf_flow(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    pdfs = catalog.get("pdfs", [])
    chosen = choose_from_list(
        pdfs,
        lambda item: f"{item.get('id')} | {item.get('title')} | {item.get('author')} | {item.get('file')}",
        "PDFs cadastrados",
    )
    if not chosen:
        return

    pdf_path = safe_repo_path(args.repo_root, chosen.get("file"))
    print("\nResumo do PDF")
    print(f"id: {chosen.get('id')}")
    print(f"título: {chosen.get('title')}")
    print(f"autor: {chosen.get('author')}")
    print(f"arquivo: {chosen.get('file')}")
    print(f"arquivo dentro do repo: {'sim' if pdf_path else 'não'}")
    print(f"existe: {'sim' if pdf_path and pdf_path.exists() else 'não'}")
    if pdf_path and pdf_path.exists():
        print(f"tamanho: {human_size(file_size(pdf_path))}")

    print("\n1) Remover apenas do catálogo")
    print("2) Remover do catálogo e apagar arquivo associado")
    print("0) Cancelar")
    action = input("Escolha: ").strip().lower()
    if action in {"0", "q"}:
        print("Operação cancelada.")
        return
    if action not in {"1", "2"}:
        print("Opção inválida.")
        return
    if action == "2" and not pdf_path:
        print("Operação recusada: caminho inválido ou fora do repositório.")
        return

    catalog["pdfs"] = [item for item in pdfs if item.get("id") != chosen.get("id")]
    if action == "2" and pdf_path and pdf_path.exists():
        pdf_path.unlink()
        parent = pdf_path.parent
        if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
            if confirm(f"A pasta {repo_relative(args.repo_root, parent)} ficou vazia. Remover pasta?", False):
                parent.rmdir()

    save_catalog(args.catalog, catalog)
    validate_catalog(args)
    print("PDF removido.")
    if post_change_menu(args, {"kind": "remove-pdf", "id": chosen.get("id"), "page": "pdf.html"}) == "exit":
        raise SystemExit(0)


def remove_album_flow(args: argparse.Namespace) -> None:
    catalog = load_catalog(args.catalog)
    albums = catalog.get("albums", [])
    chosen = choose_from_list(
        albums,
        lambda item: f"{item.get('id')} | {item.get('artist')} | {item.get('title')} | {len(item.get('tracks', []))} faixas",
        "Álbuns cadastrados",
    )
    if not chosen:
        return

    files = album_catalog_files(args.repo_root, chosen)
    existing_files = [path for path in files if path.exists() and path.is_file()]
    album_dir = probable_album_dir(args.repo_root, chosen, files)
    safe_album_dir = safe_music_dir(args.repo_root, album_dir)

    print("\nResumo do álbum")
    print(f"id: {chosen.get('id')}")
    print(f"artista: {chosen.get('artist')}")
    print(f"título: {chosen.get('title')}")
    print(f"cover: {chosen.get('cover', '')}")
    print("sources:")
    for path in files:
        print(f"- {repo_relative(args.repo_root, path) if path else '(inválido)'}")
    print(f"diretório provável: {repo_relative(args.repo_root, safe_album_dir) if safe_album_dir else '(inválido)'}")
    print(f"tamanho total existente: {human_size(sum(file_size(path) for path in existing_files))}")

    print("\n1) Remover apenas do catálogo")
    print("2) Remover do catálogo e apagar arquivos associados")
    print("3) Remover do catálogo e apagar diretório do álbum inteiro, se estiver dentro de music/")
    print("0) Cancelar")
    action = input("Escolha: ").strip().lower()
    if action in {"0", "q"}:
        print("Operação cancelada.")
        return
    if action not in {"1", "2", "3"}:
        print("Opção inválida.")
        return

    if action == "2" and any(path is None for path in files):
        print("Operação recusada: há caminhos inválidos ou fora do repositório.")
        return
    if action == "3" and not safe_album_dir:
        print("Operação recusada: diretório inválido ou fora de music/.")
        return

    catalog["albums"] = [item for item in albums if item.get("id") != chosen.get("id")]
    if action == "2":
        for path in existing_files:
            path.unlink()
    elif action == "3" and safe_album_dir and safe_album_dir.exists():
        print(f"Diretório a remover: {repo_relative(args.repo_root, safe_album_dir)}")
        for path in sorted(safe_album_dir.rglob("*"), key=natural_sort_key):
            print(f"- {repo_relative(args.repo_root, path)}")
        if input("Digite REMOVER para confirmar: ").strip() != "REMOVER":
            print("Operação cancelada.")
            return
        shutil.rmtree(safe_album_dir)

    save_catalog(args.catalog, catalog)
    validate_catalog(args)
    print("Álbum removido.")
    if post_change_menu(args, {"kind": "remove-album", "id": chosen.get("id"), "page": "album.html"}) == "exit":
        raise SystemExit(0)


def album_catalog_files(repo_root: Path, album: dict) -> list[Path | None]:
    paths: list[Path | None] = []
    cover = safe_repo_path(repo_root, album.get("cover"))
    if album.get("cover"):
        paths.append(cover)
    for track in album.get("tracks", []):
        for source in track.get("sources", []):
            paths.append(safe_repo_path(repo_root, source.get("src")))
    return paths


def probable_album_dir(repo_root: Path, album: dict, files: list[Path | None]) -> Path | None:
    valid_files = [path for path in files if path is not None]
    if valid_files:
        parents = {path.parent for path in valid_files}
        if len(parents) == 1:
            return next(iter(parents))
    artist = slugify(album.get("artist", ""))
    title = slugify(album.get("title", ""))
    if artist and title:
        return repo_root / "music" / artist / title
    return None


def browse_calibre(args: argparse.Namespace) -> dict | None:
    authors = list_top_level_dirs(args.calibre_root)
    author = choose_from_list(
        authors,
        lambda path: relative_display(args.calibre_root, path),
        "Autores / pastas principais",
    )
    if not author:
        return None

    books = sorted([path for path in author.iterdir() if path.is_dir() and not path.name.startswith(".")], key=natural_sort_key)
    book = choose_from_list(
        books,
        lambda path: relative_display(args.calibre_root, path),
        f"Livros em {author.name}",
    )
    if not book:
        return None

    pdfs = sorted(book.rglob("*.pdf"), key=natural_sort_key)
    pdf = choose_from_list(
        pdfs,
        lambda path: relative_display(args.calibre_root, path),
        f"PDFs em {book.name}",
    )
    if not pdf:
        return None
    return import_pdf_path(args, pdf)


def browse_music(args: argparse.Namespace) -> dict | None:
    artists = list_top_level_dirs(args.music_root)
    artist = choose_from_list(
        artists,
        lambda path: relative_display(args.music_root, path),
        "Artistas / pastas principais",
    )
    if not artist:
        return None
    return browse_music_dir(args, artist)


def browse_music_dir(args: argparse.Namespace, directory: Path) -> dict | None:
    current = directory
    while True:
        tracks = direct_audio_files(current)
        if tracks:
            total_size = sum(track.stat().st_size for track in tracks)
            print(f"\n{relative_display(args.music_root, current)}")
            print(f"Esta pasta parece ser um álbum: {len(tracks)} faixas | {human_size(total_size)}")
            print("1) Importar esta pasta como álbum")
            print("2) Ver subpastas")
            print("0) Voltar")
            answer = input("Escolha: ").strip().lower()
            if answer == "1":
                return import_album_dir(args, current, tracks, total_size)
            if answer in {"0", "q"}:
                return None
            if answer != "2":
                print("Opção inválida.")
                continue

        subdirs = sorted([path for path in current.iterdir() if path.is_dir() and not path.name.startswith(".")], key=natural_sort_key)
        next_dir = choose_from_list(
            subdirs,
            format_music_browse_item,
            f"Pastas em {relative_display(args.music_root, current)}",
        )
        if not next_dir:
            return None
        current = next_dir


def format_music_browse_item(path: Path) -> str:
    tracks = direct_audio_files(path)
    if tracks:
        total_size = sum(track.stat().st_size for track in tracks)
        return f"{path.name} | {len(tracks)} faixas | {human_size(total_size)}"
    return path.name


def pdf_submenu(args: argparse.Namespace) -> None:
    while True:
        print("\nPDFs / Biblioteca Calibre\n")
        print("1) Buscar PDF por termo")
        print("2) Navegar autores/pastas principais")
        print("3) Listar PDFs já cadastrados no catálogo")
        print("0) Voltar ao menu principal")
        choice = input("Escolha: ").strip().lower()

        if choice == "1":
            add_pdf_flow(args)
        elif choice == "2":
            browse_calibre(args)
        elif choice == "3":
            list_catalog_pdfs(args)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")


def music_submenu(args: argparse.Namespace) -> None:
    while True:
        print("\nMúsica / Biblioteca musical\n")
        print("1) Buscar álbum por termo")
        print("2) Navegar artistas/pastas principais")
        print("3) Listar álbuns já cadastrados no catálogo")
        print("0) Voltar ao menu principal")
        choice = input("Escolha: ").strip().lower()

        if choice == "1":
            add_album_flow(args)
        elif choice == "2":
            browse_music(args)
        elif choice == "3":
            list_catalog_albums(args)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")


def post_change_menu(args: argparse.Namespace, context: dict) -> str:
    while True:
        print("\nPós-alteração\n")
        print("1) Validar catálogo")
        print("2) Mostrar git status")
        print("3) Fazer commit")
        print("4) Fazer commit e push")
        print("5) Testar URLs locais esperadas com curl -I")
        print("8) Voltar ao menu principal")
        print("9) Sair do importador")
        print("0) Voltar ao menu principal")
        choice = input("Escolha: ").strip().lower()

        if choice == "1":
            validate_catalog(args)
        elif choice == "2":
            git_status_short(args.repo_root)
        elif choice == "3":
            git_commit_interactive(args.repo_root, context)
        elif choice == "4":
            committed_or_clean = git_commit_interactive(args.repo_root, context)
            if committed_or_clean:
                pushed = git_push_interactive(args.repo_root)
                if pushed:
                    follow_up = post_change_follow_up()
                    if follow_up:
                        return follow_up
        elif choice == "5":
            test_local_urls(args.repo_root, context)
        elif choice in {"0", "8", "q"}:
            return "menu"
        elif choice == "9":
            return "exit"
        else:
            print("Opção inválida.")


def post_change_follow_up() -> str | None:
    print("\nO que deseja fazer agora?")
    print("1) Voltar ao menu principal")
    print("2) Sair do importador")
    while True:
        answer = input("Escolha: ").strip().lower()
        if answer in {"1", "0", "q"}:
            return "menu"
        if answer == "2":
            return "exit"
        print("Opção inválida.")


def run_command(command: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=check)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", f"Comando não encontrado: {command[0]}")
    except subprocess.CalledProcessError as error:
        return error


def git_status_short(repo_root: Path) -> str:
    result = run_command(["git", "status", "--short"], repo_root)
    output = result.stdout.strip()
    print(output if output else "Sem mudanças no worktree.")
    if result.stderr.strip():
        print(result.stderr.strip())
    return output


def git_current_branch(repo_root: Path) -> str:
    result = run_command(["git", "branch", "--show-current"], repo_root)
    branch = result.stdout.strip()
    return branch or "(branch desconhecida)"


def suggested_commit_message(context: dict | None) -> str:
    if not context:
        return "Add selected library materials"
    if context.get("kind") == "pdf":
        return "Add selected PDF to pages library"
    if context.get("kind") == "album":
        return "Add selected album to pages library"
    if context.get("kind") == "remove-pdf":
        return "Remove selected PDF from pages library"
    if context.get("kind") == "remove-album":
        return "Remove selected album from pages library"
    return "Add selected library materials"


def git_commit_interactive(repo_root: Path, context: dict | None = None) -> bool:
    status = git_status_short(repo_root)
    if not status:
        print("Nada para commitar.")
        return True

    message = prompt_with_default("Mensagem de commit", suggested_commit_message(context))
    if not confirm("Confirmar git add . e git commit?", False):
        print("Commit cancelado.")
        return False

    add_result = run_command(["git", "add", "."], repo_root)
    if add_result.returncode != 0:
        print(add_result.stderr.strip() or "Falha ao executar git add.")
        return False

    commit_result = run_command(["git", "commit", "-m", message], repo_root)
    if commit_result.stdout.strip():
        print(commit_result.stdout.strip())
    if commit_result.stderr.strip():
        print(commit_result.stderr.strip())
    return commit_result.returncode == 0


def git_push_interactive(repo_root: Path) -> bool:
    branch = git_current_branch(repo_root)
    print(f"Branch atual: {branch}")
    if not confirm("Confirmar git push?", False):
        print("Push cancelado.")
        return False

    result = run_command(["git", "push"], repo_root)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        print("git push falhou.")
        return False
    return True


def test_local_urls(repo_root: Path, context: dict | None = None) -> None:
    urls = [
        "http://localhost:8000/",
        "http://localhost:8000/data/catalog.json",
    ]
    if context and context.get("page") and context.get("id"):
        urls.append(f"http://localhost:8000/{context['page']}?id={context['id']}")

    for url in urls:
        result = run_command(["curl", "-I", "--max-time", "3", url], repo_root)
        if result.returncode == 0:
            first_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else "OK"
            print(f"{url} -> {first_line}")
        else:
            print(f"{url} -> sem resposta. Inicie python3 -m http.server 8000.")


def main_menu(args: argparse.Namespace) -> None:
    while True:
        print("\nPages Library Importer\n")
        print("1) Buscar e adicionar PDF da biblioteca Calibre")
        print("2) Buscar e adicionar álbum da biblioteca musical")
        print("3) Listar PDFs já cadastrados no catálogo")
        print("4) Listar álbuns já cadastrados no catálogo")
        print("5) Validar catálogo")
        print("6) Remover item do catálogo")
        print("0) Sair")
        choice = input("Escolha: ").strip().lower()

        if choice == "1":
            pdf_submenu(args)
        elif choice == "2":
            music_submenu(args)
        elif choice == "3":
            list_catalog_pdfs(args)
        elif choice == "4":
            list_catalog_albums(args)
        elif choice == "5":
            validate_catalog(args)
        elif choice == "6":
            remove_item_submenu(args)
        elif choice in {"0", "q"}:
            print("Saindo.")
            return
        else:
            print("Opção inválida.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_repo_root = script_path.parent.parent
    parser = argparse.ArgumentParser(description="Import PDFs and albums into Pages Library.")
    parser.add_argument("--calibre-root", type=Path, default=DEFAULT_CALIBRE_ROOT, help="Calibre library root.")
    parser.add_argument("--music-root", type=Path, default=DEFAULT_MUSIC_ROOT, help="Music library root.")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root, help="Pages Library repository root.")
    parser.add_argument("--catalog", type=Path, default=None, help="Path to data/catalog.json.")
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()
    args.calibre_root = args.calibre_root.resolve()
    args.music_root = args.music_root.resolve()
    args.catalog = (args.catalog or args.repo_root / "data" / "catalog.json").resolve()
    return args


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGINT, handle_sigint)
    args = parse_args(argv or sys.argv[1:])
    try:
        load_catalog(args.catalog)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Erro ao carregar catálogo: {error}", file=sys.stderr)
        return 1

    try:
        main_menu(args)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except EOFError:
        print("\nSaindo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
