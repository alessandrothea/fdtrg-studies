# fdtrg-studies

Physics studies and validation notebooks for the DUNE Far Detector
trigger-primitive / trigger-activity chain, plus the PDF report toolkit
(`scripts/fdtrg_report/`) used by the report scripts.

This repo is **not installable** (`[tool.uv] package = false`): its
`pyproject.toml` only pins an environment. It depends on the single
**dunetrg** package — submodules `dunetrg.data`, `dunetrg.emu` and
`dunetrg.analysis` — installed from git at a pinned tag, with the `[all]`
extra so the emu and analysis stacks come along:

```toml
dependencies = ["dunetrg[all]", ...]

[tool.uv.sources]
dunetrg = { git = "…/dunetrg", rev = "v0.1.0" }
```

## Setup

```bash
cd fdtrg-studies
uv sync
export DTRG_DATA_ROOT=/path/to/data      # the directory that holds vd/, hd/, …
```

`DTRG_DATA_ROOT` is the data directory itself, so dataset paths are given
without a leading `data/`: `datacatalogue.load('vd/1x8x14/preprod')` reads
`$DTRG_DATA_ROOT/vd/1x8x14/preprod/`, where that dataset's
`datacatalogue.yaml` lives.

## Working on a library at the same time

To try a change in one of the libraries without committing anything:

```bash
uv run --with-editable ../dunetrg jupyter lab
```

To switch the source for a longer stretch of work:

```bash
make dev-link       # use ../dunetrg, editable, with the [all] extra
make dev-unlink     # back to the pinned tag
make show           # what the source is right now
```

`dev-link` edits `pyproject.toml` and `uv.lock`, so it shows up in
`git status` — don't commit it by accident. Both workflows expect the package
checkout beside this one:

```
mark_4/
├── dunetrg/            the package: src/dunetrg/{data,emu,analysis}
└── fdtrg-studies/      ← this repo
```

Once dunetrg is pushed, `make remote-github OWNER=<owner>` repoints the source
at GitHub over SSH.

## Layout

```
notebooks/1x8x14/     1x8x14 studies
notebooks/devel/      salvaged devel notebooks
marimo/               marimo apps (+ layouts/)
scripts/              batch PDF report generators
scripts/fdtrg_report/ the PDF report toolkit (pdf.py, portfolio.py, fonts/)
```

The report scripts rely on Python putting a script's own directory on
`sys.path`, so `fdtrg_report` resolves without being installed:

```bash
uv run python scripts/ar39_noise_report.py <dataset_dir> -d <dataset_name>
```

`scripts/fdtrg_report/` must never import `dunetrg` — a pre-commit hook enforces that, so the toolkit stays
movable to its own repo later.

## Running the notebooks in batch

`scripts/run_notebooks.py` executes notebooks headless and prints a
pass/fail summary (exit code 1 if any fails). Executed copies go to
`reports/notebooks/` (git-ignored), so the committed notebooks stay
output-free:

```bash
uv run python scripts/run_notebooks.py --list                 # what would run
uv run python scripts/run_notebooks.py                        # all of notebooks/
uv run python scripts/run_notebooks.py notebooks/1x8x14 -j 4  # 4 in parallel
uv run python scripts/run_notebooks.py -x 'notebooks/devel/*' -x '*-Dev*' --html
```

Other options: `--timeout` (per cell, default 3600 s), `--fail-fast`,
`--allow-errors`, `--kernel`, `-o/--output-dir`.

A notebook can end itself early, both interactively and in batch:

```python
from dunetrg.analysis.notebook import stop

if geo_file is None:
    stop("no geometry for this dataset")     # cells below are not executed
```

In Jupyter/VS Code "Run All" stops there with a one-line message and a live
kernel; in batch the notebook is reported as *stopped*, which does not count
as a failure. To skip a single cell in batch only, tag it `skip-execution`.

## Provenance

The notebooks, marimo apps and scripts were imported from
`tpvalidator@pre-split-baseline`; the libraries were split out of the same
monolith (see `MIGRATION_PLAN_v2.md` in the parent tree). Notebooks that were
not migrated stay in `tpvalidator`, frozen at that tag.
