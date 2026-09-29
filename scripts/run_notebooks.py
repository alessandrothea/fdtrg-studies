#!/usr/bin/env python
"""Execute the study notebooks in batch and report which ones run cleanly.

Executed copies are written under an output directory (default
``reports/notebooks/``, git-ignored), mirroring the source layout, so the
committed notebooks are never touched and stay output-free. Each notebook
runs with its own directory as working directory, as it would in Jupyter.

A notebook can end itself early with ``dunetrg.analysis.notebook.stop("reason")``: the
cells below stay unexecuted and the run is reported as *stopped*, not failed.

Examples::

    uv run python scripts/run_notebooks.py                     # every notebook under notebooks/
    uv run python scripts/run_notebooks.py notebooks/1x8x14 -j 4
    uv run python scripts/run_notebooks.py -x '*-Dev*' -x 'notebooks/devel/*'
    uv run python scripts/run_notebooks.py --list              # show what would run
"""

import fnmatch
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import click
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, CellTimeoutError, DeadKernelError
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = (REPO_ROOT / "notebooks",)
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "notebooks"

console = Console()


# dunetrg.analysis.notebook.stop() raises this to end a notebook early on purpose; the
# cells below it stay unexecuted and that is not a failure.
STOP_EXCEPTION = "StopExecution"


@dataclass
class RunResult:
    notebook: Path
    output: Path | None
    status: str  # 'ok', 'stopped', 'failed', 'timeout', 'dead-kernel', 'error'
    duration: float
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "stopped")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _rel(path: Path) -> Path:
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return path


def collect_notebooks(sources: tuple[Path, ...], excludes: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for src in sources:
        if src.is_dir():
            found.extend(p for p in src.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)
        elif src.suffix == ".ipynb":
            found.append(src)
        else:
            raise click.BadParameter(f"{src} is neither a directory nor a .ipynb file")

    def excluded(p: Path) -> bool:
        rel = str(_rel(p))
        return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(p.name, pat) for pat in excludes)

    # dedupe while keeping a stable order
    unique = sorted({p.resolve() for p in found})
    return [p for p in unique if not excluded(p)]


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _output_path(notebook: Path, output_dir: Path) -> Path:
    rel = _rel(notebook)
    if rel.is_absolute():
        rel = Path(rel.name)
    return output_dir / rel


def _short_error(exc: Exception) -> str:
    if isinstance(exc, CellExecutionError):
        # ename/evalue are the exception raised inside the kernel
        return f"{exc.ename}: {exc.evalue}".strip()
    return f"{type(exc).__name__}: {exc}"


def execute_notebook(
    notebook: Path,
    output_dir: Path,
    timeout: int,
    kernel: str | None,
    allow_errors: bool,
    html: bool,
) -> RunResult:
    """Run one notebook and save the executed copy (also on failure)."""
    out_path = _output_path(notebook, output_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    status, message = "ok", ""
    nb = None
    try:
        nb = nbformat.read(notebook, as_version=4)
        client = NotebookClient(
            nb,
            timeout=timeout if timeout > 0 else None,
            kernel_name=kernel or nb.metadata.get("kernelspec", {}).get("name", "python3"),
            allow_errors=allow_errors,
            resources={"metadata": {"path": str(notebook.parent)}},
        )
        client.execute()
    except CellTimeoutError as exc:
        status, message = "timeout", _short_error(exc)
    except DeadKernelError as exc:
        status, message = "dead-kernel", _short_error(exc)
    except CellExecutionError as exc:
        if exc.ename == STOP_EXCEPTION:
            status, message = "stopped", exc.evalue.strip()
        else:
            status, message = "failed", _short_error(exc)
    except Exception as exc:  # kernel start-up, unreadable notebook, ...
        status, message = "error", _short_error(exc)
        (out_path.with_suffix(".error.txt")).write_text(traceback.format_exc())
    duration = time.monotonic() - start

    if nb is None:
        return RunResult(notebook, None, status, duration, message)

    nbformat.write(nb, out_path)
    if html:
        from nbconvert import HTMLExporter

        body, _ = HTMLExporter().from_notebook_node(nb)
        out_path.with_suffix(".html").write_text(body)

    return RunResult(notebook, out_path, status, duration, message)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_STATUS_STYLE = {
    "ok": "[green]ok[/green]",
    "stopped": "[cyan]stopped[/cyan]",
    "failed": "[red]failed[/red]",
    "timeout": "[yellow]timeout[/yellow]",
    "dead-kernel": "[red]dead kernel[/red]",
    "error": "[red]error[/red]",
}


def print_summary(results: list[RunResult]) -> None:
    table = Table(title="Notebook execution summary")
    table.add_column("Notebook")
    table.add_column("Status")
    table.add_column("Time", justify="right")
    table.add_column("Details", overflow="fold")
    for r in sorted(results, key=lambda r: str(r.notebook)):
        table.add_row(str(_rel(r.notebook)), _STATUS_STYLE[r.status], f"{r.duration:.1f}s", r.message)
    console.print(table)

    n_ok = sum(r.ok for r in results)
    n_stopped = sum(r.status == "stopped" for r in results)
    colour = "green" if n_ok == len(results) else "red"
    stopped = f" ({n_stopped} stopped early)" if n_stopped else ""
    console.print(f"[{colour}]{n_ok}/{len(results)} notebooks ran successfully{stopped}[/{colour}]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("sources", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), default=DEFAULT_OUTPUT,
              show_default=True, help="Where executed copies are written (mirrors the source layout).")
@click.option("-x", "--exclude", multiple=True,
              help="Glob on the repo-relative path or file name to skip. Repeatable.")
@click.option("-j", "--jobs", type=int, default=1, show_default=True,
              help="Number of notebooks to execute in parallel.")
@click.option("-t", "--timeout", type=int, default=3600, show_default=True,
              help="Per-cell timeout in seconds (0 = no limit).")
@click.option("-k", "--kernel", default=None,
              help="Kernel name to use instead of the one stored in each notebook.")
@click.option("--allow-errors", is_flag=True,
              help="Keep executing cells after an error (the notebook is still reported ok).")
@click.option("--fail-fast", is_flag=True, help="Stop at the first notebook that fails.")
@click.option("--html", is_flag=True, help="Also export each executed notebook to HTML.")
@click.option("-l", "--list", "list_only", is_flag=True, help="List the notebooks that would run and exit.")
def main(sources, output_dir, exclude, jobs, timeout, kernel, allow_errors, fail_fast, html, list_only):
    """Execute notebooks in SOURCES (files or directories; default: notebooks/)."""
    notebooks = collect_notebooks(sources or DEFAULT_SOURCES, exclude)
    if not notebooks:
        console.print("[yellow]No notebooks found.[/yellow]")
        return

    if list_only:
        for nb in notebooks:
            console.print(str(_rel(nb)))
        console.print(f"[bold]{len(notebooks)}[/bold] notebooks")
        return

    if "DTRG_DATA_ROOT" not in os.environ:
        console.print("[yellow]warning:[/yellow] DTRG_DATA_ROOT is not set; data-loading notebooks will fail.")

    output_dir = output_dir.resolve()
    console.print(f"Running [bold]{len(notebooks)}[/bold] notebooks, output in {output_dir}")

    run_args = dict(output_dir=output_dir, timeout=timeout, kernel=kernel,
                    allow_errors=allow_errors, html=html)
    results: list[RunResult] = []

    def report(r: RunResult) -> None:
        results.append(r)
        console.print(f"  {_STATUS_STYLE[r.status]}  {_rel(r.notebook)}  ({r.duration:.1f}s)")

    if jobs <= 1:
        for nb in notebooks:
            console.print(f"[dim]→ {_rel(nb)}[/dim]")
            r = execute_notebook(nb, **run_args)
            report(r)
            if fail_fast and not r.ok:
                break
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(execute_notebook, nb, **run_args) for nb in notebooks]
            for fut in as_completed(futures):
                r = fut.result()
                report(r)
                if fail_fast and not r.ok:
                    for f in futures:
                        f.cancel()
                    break

    print_summary(results)
    sys.exit(0 if all(r.ok for r in results) and len(results) == len(notebooks) else 1)


if __name__ == "__main__":
    main()
