#!/usr/bin/env python3
"""Interactive importer for the static Pages Library catalog."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


DEFAULT_CALIBRE_ROOT = Path("/srv/media/calibre-library")
DEFAULT_MUSIC_ROOT = Path("/srv/media/music")
GITHUB_PAGES_BASE = "https://rib-thiago.github.io/pages-library"
MAX_RESULTS = 30
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
        if needle in str(path).casefold():
            results.append(path)
            if len(results) >= MAX_RESULTS:
                break
    return sorted(results, key=natural_sort_key)


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
        answer = input("Escolha um número ou 0 para cancelar: ").strip()
        if answer == "0":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(results):
            return results[int(answer) - 1]
        print("Opção inválida.")


def catalog_id_exists(catalog: dict, item_id: str) -> bool:
    return any(item.get("id") == item_id for item in catalog.get("pdfs", [])) or any(
        item.get("id") == item_id for item in catalog.get("albums", [])
    )


def repo_relative(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def prompt_action() -> str:
    print("\nAplicar operação?")
    print("1) Copiar arquivos e atualizar catálogo")
    print("2) Dry-run: mostrar o que faria")
    print("0) Cancelar")
    while True:
        answer = input("Escolha: ").strip()
        if answer in {"1", "2", "0"}:
            return answer
        print("Opção inválida.")


def add_pdf_flow(args: argparse.Namespace) -> None:
    term = input("Termo de busca para PDF: ").strip()
    if not term:
        print("Busca cancelada.")
        return

    results = search_pdfs(args.calibre_root, term)
    chosen = choose_result(results, lambda path: str(path))
    if not chosen:
        return

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
        return

    author_slug = slugify(author or "autor-desconhecido")
    title_slug = slugify(title or chosen.stem)
    destination_dir = args.repo_root / "pdfs" / author_slug
    destination_file = destination_dir / f"{title_slug}.pdf"

    overwrite = False
    if destination_file.exists():
        overwrite = confirm(f"O arquivo de destino já existe: {destination_file}. Sobrescrever explicitamente?", False)
        if not overwrite:
            print("Operação cancelada.")
            return

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
        return
    if action == "2":
        print("Dry-run concluído. Nenhum arquivo foi copiado e o catálogo não foi alterado.")
        return

    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen, destination_file)
    catalog["pdfs"].append(item)
    save_catalog(args.catalog, catalog)
    print("PDF importado com sucesso.")
    print_urls("pdf.html", item_id)


def print_pdf_summary(source: Path, destination: Path, item: dict) -> None:
    print("\nResumo da importação do PDF")
    print(f"Origem: {source}")
    print(f"Destino: {destination}")
    print(f"Tamanho: {human_size(source.stat().st_size)}")
    print(f"Entrada: {json.dumps(item, ensure_ascii=False, indent=2)}")
    print_urls("pdf.html", item["id"])


def add_album_flow(args: argparse.Namespace) -> None:
    term = input("Termo de busca para álbum: ").strip()
    if not term:
        print("Busca cancelada.")
        return

    results = search_album_dirs(args.music_root, term)
    chosen = choose_result(
        results,
        lambda item: f"{item[0]} | {len(item[1])} faixas | {human_size(item[2])}",
    )
    if not chosen:
        return

    album_dir, tracks, total_size = chosen
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
        return

    destination_dir = args.repo_root / "music" / slugify(artist or "artista-desconhecido") / slugify(title or album_dir.name)
    overwrite = False
    if destination_dir.exists():
        overwrite = confirm(f"O diretório de destino já existe: {destination_dir}. Sobrescrever explicitamente?", False)
        if not overwrite:
            print("Operação cancelada.")
            return

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
        return
    if action == "2":
        print("Dry-run concluído. Nenhum arquivo foi copiado e o catálogo não foi alterado.")
        return

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


def main_menu(args: argparse.Namespace) -> None:
    while True:
        print("\nPages Library Importer\n")
        print("1) Buscar e adicionar PDF da biblioteca Calibre")
        print("2) Buscar e adicionar álbum da biblioteca musical")
        print("3) Listar PDFs já cadastrados no catálogo")
        print("4) Listar álbuns já cadastrados no catálogo")
        print("5) Validar catálogo")
        print("0) Sair")
        choice = input("Escolha: ").strip()

        if choice == "1":
            add_pdf_flow(args)
        elif choice == "2":
            add_album_flow(args)
        elif choice == "3":
            list_catalog_pdfs(args)
        elif choice == "4":
            list_catalog_albums(args)
        elif choice == "5":
            validate_catalog(args)
        elif choice == "0":
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
    args = parse_args(argv or sys.argv[1:])
    try:
        load_catalog(args.catalog)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Erro ao carregar catálogo: {error}", file=sys.stderr)
        return 1

    main_menu(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
