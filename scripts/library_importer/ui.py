from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Sequence

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None

from .config import PAGE_SIZE


def print_msg(message: str = "", style: str | None = None) -> None:
    if HAS_RICH:
        console.print(message, style=style)
    else:
        print(message)


def panel(title: str, body: str, style: str = "cyan") -> None:
    if HAS_RICH:
        console.print(Panel(body, title=title, border_style=style))
    else:
        print(f"\n{title}")
        if body:
            print(body)


def table(title: str, columns: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    rows = list(rows)
    if HAS_RICH:
        rich_table = Table(title=title, show_lines=False)
        for column in columns:
            rich_table.add_column(column)
        for row in rows:
            rich_table.add_row(*[str(value) for value in row])
        console.print(rich_table)
        return
    print(f"\n{title}")
    print(" | ".join(columns))
    print("-" * 80)
    for row in rows:
        print(" | ".join(str(value) for value in row))


def truncate_text(value: str | None, limit: int = 72) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def short_path(path: Path | str, root: Path | None = None, limit: int = 72) -> str:
    path_obj = Path(path)
    if root:
        try:
            text = path_obj.relative_to(root).as_posix()
        except ValueError:
            text = str(path)
    else:
        text = str(path)
    return truncate_text(text, limit)


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


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def render_menu(title: str, options: Sequence[tuple[str, str]], body: str = "", style: str = "cyan") -> None:
    panel(title, body, style)
    for key, label in options:
        if key != "0":
            print_msg(f"{key}) {label}")
    zero = next((label for key, label in options if key == "0"), None)
    if zero:
        print_msg(f"0) {zero}", "dim")


def choose_from_list(
    items: Sequence,
    title: str,
    columns: Sequence[str],
    row_builder: Callable[[int, object], Sequence[str]],
    page_size: int = PAGE_SIZE,
):
    if not items:
        print_msg("Nenhuma entrada encontrada.", "yellow")
        return None
    page = 0
    total_pages = (len(items) + page_size - 1) // page_size
    while True:
        start = page * page_size
        page_items = list(items[start : start + page_size])
        rows = [row_builder(index, item) for index, item in enumerate(page_items, start=1)]
        table(f"{title} - Página {page + 1}/{total_pages}", columns, rows)
        print("n = próxima, p = anterior, 0 = voltar")
        answer = input("Escolha: ").strip().lower()
        if answer in {"0", "q"}:
            return None
        if answer == "n":
            page = min(page + 1, total_pages - 1)
            continue
        if answer == "p":
            page = max(page - 1, 0)
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(page_items):
            return page_items[int(answer) - 1]
        print("Opção inválida.")

