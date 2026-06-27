from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from .catalog import list_catalog_albums, list_catalog_pdfs, show_catalog_validation
from .config import AppConfig, DEFAULT_CALIBRE_ROOT, DEFAULT_MUSIC_ROOT
from .git_ops import git_commit_interactive, git_push_interactive, git_status_short, run_command
from .import_ops import import_album, import_pdf
from .media_scan import browse_label, direct_audio_files, list_top_level_dirs, search_album_dirs, search_pdfs
from .paths import human_size, natural_sort_key, relative_display
from .remove_ops import remove_album_flow, remove_pdf_flow
from .ui import choose_from_list, render_menu, short_path


def handle_sigint(signum, frame) -> None:
    print("\nInterrompido pelo usuário.")
    raise SystemExit(0)


def parse_args(argv: list[str]) -> AppConfig:
    script_path = Path(__file__).resolve()
    default_repo_root = script_path.parents[2]
    parser = argparse.ArgumentParser(description="Import PDFs and albums into Pages Library.")
    parser.add_argument("--calibre-root", type=Path, default=DEFAULT_CALIBRE_ROOT, help="Calibre library root.")
    parser.add_argument("--music-root", type=Path, default=DEFAULT_MUSIC_ROOT, help="Music library root.")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root, help="Pages Library repository root.")
    parser.add_argument("--catalog", type=Path, default=None, help="Path to data/catalog.json.")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    return AppConfig(
        repo_root=repo_root,
        catalog=(args.catalog or repo_root / "data" / "catalog.json").resolve(),
        calibre_root=args.calibre_root.resolve(),
        music_root=args.music_root.resolve(),
    )


def post_change_menu(config: AppConfig, context: dict) -> str:
    while True:
        render_menu(
            "Pós-alteração",
            [
                ("1", "Validar catálogo"),
                ("2", "Mostrar git status"),
                ("3", "Fazer commit"),
                ("4", "Fazer commit e push"),
                ("5", "Testar URLs locais esperadas com curl -I"),
                ("8", "Voltar ao menu principal"),
                ("9", "Sair do importador"),
                ("0", "Voltar ao menu principal"),
            ],
        )
        choice = input("Escolha: ").strip().lower()
        if choice == "1":
            show_catalog_validation(config.catalog)
        elif choice == "2":
            git_status_short(config.repo_root)
        elif choice == "3":
            git_commit_interactive(config.repo_root, context)
        elif choice == "4":
            if git_commit_interactive(config.repo_root, context) and git_push_interactive(config.repo_root):
                answer = input("1) Voltar ao menu principal  2) Sair: ").strip()
                return "exit" if answer == "2" else "menu"
        elif choice == "5":
            test_local_urls(config, context)
        elif choice in {"0", "8", "q"}:
            return "menu"
        elif choice == "9":
            return "exit"
        else:
            print("Opção inválida.")


def test_local_urls(config: AppConfig, context: dict | None = None) -> None:
    urls = ["http://localhost:8000/", "http://localhost:8000/data/catalog.json"]
    if context and context.get("page") and context.get("id"):
        urls.append(f"http://localhost:8000/{context['page']}?id={context['id']}")
    for url in urls:
        result = run_command(["curl", "-I", "--max-time", "3", url], config.repo_root)
        if result.returncode == 0:
            print(f"{url} -> {result.stdout.splitlines()[0] if result.stdout.splitlines() else 'OK'}")
        else:
            print(f"{url} -> sem resposta. Inicie python3 -m http.server 8000.")


def pdf_submenu(config: AppConfig) -> None:
    while True:
        render_menu(
            "PDFs / Biblioteca Calibre",
            [
                ("1", "Buscar PDF por termo"),
                ("2", "Navegar autores/pastas principais"),
                ("3", "Listar PDFs já cadastrados no catálogo"),
                ("0", "Voltar ao menu principal"),
            ],
            "Busque por termo ou navegue pela biblioteca Calibre antes de importar.",
        )
        choice = input("Escolha: ").strip().lower()
        context = None
        if choice == "1":
            term = input("Termo de busca para PDF: ").strip()
            if term:
                results = search_pdfs(config.calibre_root, term)
                pdf = choose_from_list(results, "Resultados", ["nº", "arquivo", "pasta"], lambda i, p: [str(i), p.name, relative_display(config.calibre_root, p.parent)])
                if pdf:
                    context = import_pdf(config, pdf)
        elif choice == "2":
            context = browse_calibre(config)
        elif choice == "3":
            list_catalog_pdfs(config.catalog, config.repo_root)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")
        if context and post_change_menu(config, context) == "exit":
            raise SystemExit(0)


def browse_calibre(config: AppConfig) -> dict | None:
    authors = list_top_level_dirs(config.calibre_root)
    author = choose_from_list(authors, "Autores / pastas principais", ["nº", "autor"], lambda i, p: [str(i), browse_label(config.calibre_root, p)])
    if not author:
        return None
    books = sorted([path for path in author.iterdir() if path.is_dir() and not path.name.startswith(".")], key=natural_sort_key)
    book = choose_from_list(books, f"Livros em {author.name}", ["nº", "livro"], lambda i, p: [str(i), p.name])
    if not book:
        return None
    pdfs = sorted(book.rglob("*.pdf"), key=natural_sort_key)
    pdf = choose_from_list(pdfs, f"PDFs em {book.name}", ["nº", "arquivo"], lambda i, p: [str(i), p.name])
    return import_pdf(config, pdf) if pdf else None


def music_submenu(config: AppConfig) -> None:
    while True:
        render_menu(
            "Música / Biblioteca musical",
            [
                ("1", "Buscar álbum por termo"),
                ("2", "Navegar artistas/pastas principais"),
                ("3", "Listar álbuns já cadastrados no catálogo"),
                ("0", "Voltar ao menu principal"),
            ],
            "Busque por termo ou navegue pela biblioteca musical antes de importar.",
        )
        choice = input("Escolha: ").strip().lower()
        context = None
        if choice == "1":
            term = input("Termo de busca para álbum: ").strip()
            if term:
                results = search_album_dirs(config.music_root, term)
                album = choose_from_list(
                    results,
                    "Resultados",
                    ["nº", "pasta", "faixas", "tamanho"],
                    lambda i, item: [str(i), relative_display(config.music_root, item[0]), str(len(item[1])), human_size(item[2])],
                )
                if album:
                    context = import_album(config, album[0], album[1])
        elif choice == "2":
            context = browse_music(config)
        elif choice == "3":
            list_catalog_albums(config.catalog, config.repo_root)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")
        if context and post_change_menu(config, context) == "exit":
            raise SystemExit(0)


def browse_music(config: AppConfig) -> dict | None:
    artists = list_top_level_dirs(config.music_root)
    artist = choose_from_list(artists, "Artistas / pastas principais", ["nº", "artista"], lambda i, p: [str(i), browse_label(config.music_root, p)])
    return browse_music_dir(config, artist) if artist else None


def browse_music_dir(config: AppConfig, directory: Path) -> dict | None:
    current = directory
    while True:
        tracks = direct_audio_files(current)
        if tracks:
            print(f"\n{relative_display(config.music_root, current)}")
            print(f"Esta pasta parece ser um álbum: {len(tracks)} faixas | {human_size(sum(t.stat().st_size for t in tracks))}")
            print("1) Importar esta pasta como álbum")
            print("2) Ver subpastas")
            print("0) Voltar")
            answer = input("Escolha: ").strip().lower()
            if answer == "1":
                return import_album(config, current, tracks)
            if answer in {"0", "q"}:
                return None
            if answer != "2":
                print("Opção inválida.")
                continue
        subdirs = sorted([path for path in current.iterdir() if path.is_dir() and not path.name.startswith(".")], key=natural_sort_key)
        next_dir = choose_from_list(subdirs, f"Pastas em {relative_display(config.music_root, current)}", ["nº", "pasta"], lambda i, p: [str(i), p.name])
        if not next_dir:
            return None
        current = next_dir


def remove_submenu(config: AppConfig) -> None:
    while True:
        render_menu(
            "Remover item",
            [("1", "Remover PDF"), ("2", "Remover álbum"), ("0", "Voltar")],
            "Remova entradas do catálogo e, opcionalmente, cópias publicadas dentro do repo.",
        )
        choice = input("Escolha: ").strip().lower()
        context = None
        if choice == "1":
            context = remove_pdf_flow(config)
        elif choice == "2":
            context = remove_album_flow(config)
        elif choice in {"0", "q"}:
            return
        else:
            print("Opção inválida.")
        if context and post_change_menu(config, context) == "exit":
            raise SystemExit(0)


def main_menu(config: AppConfig) -> None:
    while True:
        render_menu(
            "Pages Library Importer",
            [
                ("1", "Buscar e adicionar PDF da biblioteca Calibre"),
                ("2", "Buscar e adicionar álbum da biblioteca musical"),
                ("3", "Listar PDFs já cadastrados no catálogo"),
                ("4", "Listar álbuns já cadastrados no catálogo"),
                ("5", "Validar catálogo"),
                ("6", "Remover item do catálogo"),
                ("0", "Sair"),
            ],
            f"Repo: {config.repo_root}\nCatálogo: {short_path(config.catalog, config.repo_root)}",
        )
        choice = input("Escolha: ").strip().lower()
        if choice == "1":
            pdf_submenu(config)
        elif choice == "2":
            music_submenu(config)
        elif choice == "3":
            list_catalog_pdfs(config.catalog, config.repo_root)
        elif choice == "4":
            list_catalog_albums(config.catalog, config.repo_root)
        elif choice == "5":
            show_catalog_validation(config.catalog)
        elif choice == "6":
            remove_submenu(config)
        elif choice in {"0", "q"}:
            print("Saindo.")
            return
        else:
            print("Opção inválida.")


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGINT, handle_sigint)
    config = parse_args(argv or sys.argv[1:])
    try:
        main_menu(config)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    except EOFError:
        print("\nSaindo.")
    return 0
