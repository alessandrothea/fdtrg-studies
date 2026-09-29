#!/usr/bin/env python
"""Write a .env with DTRG_DATA_ROOT and point VS Code's notebook kernels at it.

The VS Code Jupyter extension loads the file named by the ``python.envFile``
setting into every Python kernel it starts. This script

1. creates or updates the env file (default: ``fdtrg-studies/.env``), setting
   ``DTRG_DATA_ROOT`` and keeping any other variables already in it;
2. sets ``python.envFile`` in ``<workspace>/.vscode/settings.json``, where
   ``<workspace>`` is the folder you open in VS Code (the repo itself, or a
   parent directory that contains it). Other settings are kept.

Examples::

    uv run python scripts/setup_vscode_env.py --data-root /path/to/data
    uv run python scripts/setup_vscode_env.py -d /path/to/data -w ..      # workspace = parent dir
    uv run python scripts/setup_vscode_env.py -d /path/to/data --no-vscode
    uv run python scripts/setup_vscode_env.py -d /path/to/data --dry-run

Restart the notebook kernels (or reload the VS Code window) afterwards.
"""

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parent.parent
VAR = "DTRG_DATA_ROOT"
SETTING = "python.envFile"

console = Console()


def _updated_env_text(env_file: Path, data_root: Path) -> str:
    """Return the env file contents with VAR set, keeping every other line."""
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    new_line = f"{VAR}={data_root}"
    out, replaced = [], False
    for line in lines:
        key = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if key == VAR:
            if not replaced:
                out.append(new_line)
                replaced = True
            continue
        out.append(line)
    if not replaced:
        out.append(new_line)
    return "\n".join(out) + "\n"


def _env_file_setting(env_file: Path, workspace: Path) -> str:
    """Express the env file path relative to ${workspaceFolder} when possible."""
    try:
        return "${workspaceFolder}/" + env_file.relative_to(workspace).as_posix()
    except ValueError:
        return str(env_file)


def _check_data_root(data_root: Path) -> None:
    if not data_root.is_dir():
        raise click.BadParameter(f"{data_root} is not a directory", param_hint="--data-root")
    if not any((data_root / d).is_dir() for d in ("vd", "hd")):
        console.print(f"[yellow]warning:[/yellow] {data_root} has no vd/ or hd/ subdirectory; "
                      "is it really the data root?")


def _ask_workspace() -> Path:
    candidates = [REPO_ROOT, REPO_ROOT.parent]
    console.print("Which folder do you open in VS Code? .vscode/settings.json goes there.")
    for i, c in enumerate(candidates, 1):
        console.print(f"  [bold]{i}[/bold]) {c}")
    console.print("  or type another path")
    answer = click.prompt("Workspace", default="1")
    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1]
    return Path(answer).expanduser()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-d", "--data-root", type=click.Path(path_type=Path), default=None,
              help=f"Data directory (holds vd/, hd/). Defaults to ${VAR} if set, else asks.")
@click.option("-e", "--env-file", type=click.Path(path_type=Path), default=REPO_ROOT / ".env",
              show_default=True, help="Env file to create or update.")
@click.option("-w", "--workspace", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="VS Code workspace folder that gets .vscode/settings.json. Asks if omitted.")
@click.option("--no-vscode", is_flag=True, help="Only write the env file.")
@click.option("--force", is_flag=True, help=f"Replace an existing, different '{SETTING}' setting.")
@click.option("-n", "--dry-run", is_flag=True, help="Show what would be written, change nothing.")
def main(data_root, env_file, workspace, no_vscode, force, dry_run):
    """Set up DTRG_DATA_ROOT for notebooks run in VS Code."""
    if data_root is None:
        data_root = Path(os.environ[VAR]) if VAR in os.environ else Path(click.prompt("Data root"))
    data_root = data_root.expanduser().resolve()
    _check_data_root(data_root)
    env_file = env_file.expanduser().resolve()

    settings_file, settings = None, None
    if not no_vscode:
        if workspace is None:
            workspace = _ask_workspace() if sys.stdin.isatty() else REPO_ROOT
        workspace = workspace.expanduser().resolve()
        if not workspace.is_dir():
            raise click.BadParameter(f"{workspace} is not a directory", param_hint="--workspace")

        settings_file = workspace / ".vscode" / "settings.json"
        settings = {}
        if settings_file.exists():
            try:
                settings = json.loads(settings_file.read_text() or "{}")
            except json.JSONDecodeError:
                # VS Code allows comments/trailing commas; don't risk mangling the file
                console.print(f"[red]error:[/red] {settings_file} is not plain JSON (comments?). "
                              f"Add this entry by hand:\n"
                              f'    "{SETTING}": "{_env_file_setting(env_file, workspace)}"')
                sys.exit(1)

        value = _env_file_setting(env_file, workspace)
        current = settings.get(SETTING)
        if current not in (None, value) and not force:
            console.print(f"[red]error:[/red] {settings_file} already sets {SETTING} = {current!r}. "
                          "Use --force to replace it.")
            sys.exit(1)
        settings[SETTING] = value

    env_text = _updated_env_text(env_file, data_root)
    settings_text = json.dumps(settings, indent=4) + "\n" if settings is not None else None

    if dry_run:
        console.rule(str(env_file))
        console.print(env_text, end="", markup=False)
        if settings_file:
            console.rule(str(settings_file))
            console.print(settings_text, end="", markup=False)
        return

    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(env_text)
    console.print(f"[green]wrote[/green] {env_file}")
    if settings_file:
        settings_file.parent.mkdir(exist_ok=True)
        settings_file.write_text(settings_text)
        console.print(f"[green]wrote[/green] {settings_file}  ({SETTING} = {settings[SETTING]})")
        console.print("Restart the notebook kernels (or reload the VS Code window) to pick it up.")

    console.print(f"[yellow]note:[/yellow] keep {env_file.name} out of git; it holds a machine-specific path.")


if __name__ == "__main__":
    main()
