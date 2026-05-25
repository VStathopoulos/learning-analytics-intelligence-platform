# Setup

Early local setup guide for the Learning Analytics Intelligence Platform.

## 1. Prerequisites

- Conda or Miniconda installed locally.
- Git installed locally.
- VS Code installed if using Codex-assisted development.
- Project dependencies are managed through `environment.yml`.

The project uses Python 3.11 with DuckDB, dbt-duckdb, Dash/Plotly, pytest,
ruff, and black.

## 2. Clone Or Open The Project Folder

Use the project root as the working directory:

```bash
cd ~/projects/learning-analytics-intelligence-platform
```

If cloning on a new machine, clone the repository first, then open the cloned
project root in VS Code.

## 3. Create The Conda Environment

Create the local Conda environment from the checked-in environment file:

```bash
conda env create -f environment.yml
```

If the environment already exists, use `conda env update -f environment.yml --prune`.

The expected environment name is:

```bash
laip
```

## 4. Activate The Environment

```bash
conda activate laip
```

Verify the Python version:

```bash
python --version
```

Expected major/minor version:

```text
Python 3.11
```

## 5. Verify Python Analytics Stack

Run a quick import check:

```bash
python -c "import duckdb, dash, plotly; print('analytics stack ok')"
```

## 6. Verify dbt-duckdb

Check that dbt is available and can see the DuckDB adapter:

```bash
dbt --version
```

The output should include dbt core and the DuckDB adapter.

## 7. Run Code Quality Checks

Run formatting and lint checks from the project root:

```bash
black --check .
ruff check .
```

pytest will be added to the verification workflow once the first tests are
implemented.

## 8. Airflow Status

Airflow is intentionally deferred and should not be installed during the initial
setup. The `orchestration/` folder is reserved for future Airflow DAGs.

## 9. Codex Safety Notes

When using Codex in VS Code, open only this project root:

```text
~/projects/learning-analytics-intelligence-platform
```

Do not open the broader `~/projects` directory as the workspace.

## 10. Expected Project Paths

- Project root: `~/projects/learning-analytics-intelligence-platform`
- Conda environment: `laip`
- Raw OULAD data directory: `data/raw/`
- DuckDB warehouse path: `data/warehouse/laip.duckdb`
- dbt project directory: `dbt/`
- Dash application directory: `dashboard/`
- LLM insight layer directory: `insights/`
