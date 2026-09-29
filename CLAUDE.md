# fdtrg-studies — context for agents

## What this is

Physics studies (notebooks, marimo apps, batch report scripts) for the DUNE
trigger-primitive / trigger-activity chain. **Not installable**
(`[tool.uv] package = false`): `pyproject.toml` only defines an environment.
Depends on `dunetrg-data`, `dunetrg-emu` and `dunetrg-analysis`, which are
members of the **dunetrg workspace repo**; each is installed from its
subdirectory (`packages/<name>`) at a pinned tag, so `uv sync` works without
a sibling checkout. To develop against a local workspace, use
`uv run --with-editable ../dunetrg/packages/<name> <cmd>` for a single
command, or `make dev-link` / `make dev-unlink`, which switch all three at once (linking
just one cannot resolve: a pinned package wants `dunetrg-data` from git while
a linked workspace member wants the local path). They edit `pyproject.toml`
and `uv.lock`, so don't commit them by accident.

## Toolchain

- `uv` for everything: `uv sync`, `uv run python scripts/...`,
  `uv run jupyter lab`, `uv run marimo edit marimo/<app>.py`.
- Python 3.13 (`.python-version`).

## Layout

```
notebooks/1x8x14/       1x8x14 studies
notebooks/devel/        salvaged devel notebooks
marimo/                 marimo apps + layouts/
scripts/                batch PDF report generators
scripts/fdtrg_report/    PDF report toolkit (pdf.py, portfolio.py, fonts/)
```

`scripts/fdtrg_report/` is a plain, non-installed directory. Python puts a
script's own directory on `sys.path`, so `scripts/ar39_noise_report.py` can
do `from fdtrg_report.pdf import ReportPDF` without an install step. Any
notebook or marimo app that needs the report toolkit has to add `scripts/` to
`sys.path` itself first (none currently do).

**Rule (enforced by pre-commit, migration plan §3 rule 3):**
`scripts/fdtrg_report/` must never import `dunetrg.data`, `dunetrg.emu` or
`dunetrg.analysis` — that keeps it movable to its own repo later.

## Data

Data is external, at `$DTRG_DATA_ROOT` (the directory that used to be
`tpvalidator/data/`). `dunetrg.data.datacatalogue` resolves relative dataset
directories against it directly, so pass paths like `'vd/1x8x14/preprod'`
(no leading `data/`) to `load()` / `load_datasets()` / etc.

Some paths inherited from `tpvalidator` don't resolve cleanly under
`DTRG_DATA_ROOT` today (stale directory names, or files that live outside the
`vd/`/`hd/` tree). These are marked `# TODO(migration): ...` in place — grep
for that tag before assuming a notebook runs end-to-end.

## Notebook hygiene

**Always strip notebook outputs before committing.** `nbstripout` is wired
up as a pre-commit hook; if you're editing notebooks outside of a commit
flow, strip explicitly:

```bash
uv run --with nbstripout nbstripout notebooks/**/*.ipynb
```

Never commit executed notebooks with large embedded outputs (images, dataframes).

To check notebooks run end-to-end, use `uv run python scripts/run_notebooks.py`
(see README): it writes executed copies to `reports/notebooks/` and never
modifies the sources.

## Import naming

This repo's notebooks/scripts/marimo apps import `dunetrg.data`, `dunetrg.emu`,
`dunetrg.analysis` — never the old `tpvalidator` package, which no longer
exists here. If you see a `tpvalidator.*` import, it's a leftover that needs
rewriting (see `../tools/rewrite_imports.py` in the parent `mark_2/`
directory, and `MIGRATION_PLAN_v2.md` §7.3 for the mapping table).
