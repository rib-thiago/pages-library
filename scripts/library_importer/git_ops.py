from __future__ import annotations

import subprocess
from pathlib import Path

from .ui import confirm, panel, prompt_with_default, table, truncate_text


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", f"Comando não encontrado: {command[0]}")


def git_status_short(repo_root: Path) -> str:
    result = run_command(["git", "status", "--short"], repo_root)
    output = result.stdout.strip()
    if not output:
        panel("Mudanças pendentes", "Sem mudanças no worktree.", "green")
        return ""
    rows = []
    for line in output.splitlines():
        status = line[:2]
        path = line[3:] if len(line) > 3 else line
        if "D" in status:
            kind = "removido"
        elif "??" in status or "A" in status:
            kind = "novo"
        elif "M" in status:
            kind = "modificado"
        else:
            kind = "outro"
        rows.append([kind, truncate_text(path, 88)])
    table("Mudanças pendentes", ["tipo", "arquivo"], rows)
    return output


def git_current_branch(repo_root: Path) -> str:
    result = run_command(["git", "branch", "--show-current"], repo_root)
    return result.stdout.strip() or "(branch desconhecida)"


def suggested_commit_message(context: dict | None) -> str:
    if not context:
        return "Add selected library materials"
    return {
        "pdf": "Add selected PDF to pages library",
        "album": "Add selected album to pages library",
        "remove-pdf": "Remove selected PDF from pages library",
        "remove-album": "Remove selected album from pages library",
    }.get(context.get("kind"), "Add selected library materials")


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
    print(f"Branch atual: {git_current_branch(repo_root)}")
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

