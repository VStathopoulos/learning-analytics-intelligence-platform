# Learning Analytics Intelligence Platform

The Learning Analytics Intelligence Platform is an analytics engineering and BI
portfolio project built on OULAD data. It creates a local DuckDB and dbt-powered
analytics platform for online learning engagement, assessment performance, course
health, withdrawal patterns, and rule-based student-success risk signals.

The project is designed for transparent learning analytics: raw data is
validated and modeled into documented dbt marts, and the dashboard consumes only
approved mart tables rather than raw, staging, or intermediate data.

## Key Business Questions

- How does learner engagement evolve across course presentations?
- Are declining-engagement students more likely to withdraw?
- Do low-engagement students score lower?
- Which anonymized student-module attempts show multiple rule-based risk signals?
- How can course teams monitor engagement, assessment performance, and
  student-success indicators?

## Current Features

- Raw OULAD file validation for required files and schemas.
- Local DuckDB warehouse for reproducible analytics development.
- dbt staging, intermediate, and mart layers using dbt-duckdb.
- Documented and tested dbt models.
- Dash and Plotly dashboard for course and student-success analytics.
- Student-success feature mart combining demographics, outcomes, engagement,
  assessment behavior, and rule-based risk indicators.
- Rule-based risk segmentation for analytical monitoring.
- Dashboard reads only approved dbt mart tables.

## Architecture

```text
OULAD raw CSVs
-> Python validation
-> DuckDB raw tables
-> dbt sources
-> dbt staging models
-> dbt intermediate models
-> dbt marts
-> Dash dashboard
-> governed future LLM insight cards
```

The governed LLM insight card layer is planned future work and is not currently
implemented.

## Data Source

This project uses the Open University Learning Analytics Dataset (OULAD). Raw
CSV files are stored locally under `data/raw/` and are not committed to Git.

## dbt Model Layers

- `staging`: typed and standardized source-aligned views.
- `intermediate`: reusable joins and learning activity logic.
- `marts`: dashboard-ready business tables.
- `student-success marts`: engagement, assessment, and rule-based risk feature
  tables for student-success analysis.

Current dbt status:

- 16 dbt models.
- 127 dbt data tests.
- 7 raw sources.
- Student-success feature mart documented and tested.

Important implemented mart models include:

- `dim_student_module`
- `fct_course_engagement_daily`
- `fct_assessment_performance`
- `fct_student_engagement_summary`
- `fct_student_assessment_summary`
- `mart_student_success_features`

## Dashboard

The Dash dashboard reads from approved dbt mart tables in DuckDB and includes:

- Module and presentation filters.
- Enrollment and withdrawal KPIs.
- Engagement trends.
- Assessment performance.
- Final-result distribution.
- Risk-band distribution.
- Withdrawal rate by risk band.
- Declining engagement vs withdrawal rate.
- Low engagement vs average score.
- Highest-risk anonymized student-module attempts table.

The dashboard directly supports these student-success questions:

- Did students with declining engagement have higher withdrawal rates?
- Did low-engagement students score lower?
- Which anonymized student-module attempts show multiple risk signals?

## Screenshots

Screenshots will be added after the dashboard layout is finalized.

## How To Run Locally

Create and activate the Conda environment:

```bash
conda env create -f environment.yml
conda activate laip
```

Validate and load the local raw OULAD data:

```bash
python ingestion/validate_raw_data.py
python ingestion/load_raw_to_duckdb.py
```

Build and test the dbt project:

```bash
cd dbt
dbt debug --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
cd ..
```

Run the dashboard:

```bash
python dashboard/app.py
```

Then open:

```text
http://127.0.0.1:8050/
```

## Repository Hygiene

- Raw CSV files are ignored.
- DuckDB warehouse files are ignored.
- dbt `target/` and `logs/` artifacts are ignored.
- `.env` files are ignored.
- Only code, configuration, and documentation are committed.

## LLM Insight Governance

LLM insight generation is planned and governed, but it is not currently
implemented as a production feature. Future LLM components must consume only
approved aggregate marts or dashboard summary tables. Raw student-level records
must not be passed to the LLM.

## Current Limitations

- Risk bands are rule-based analytical indicators, not validated predictive ML
  outputs.
- The application is not deployed yet.
- Airflow orchestration is planned but not implemented yet.
- Screenshots still need to be added.
- Future work may include CI, an Airflow DAG, and governed LLM insight cards.

## Suggested Portfolio Positioning

This project demonstrates analytics engineering, dbt modeling, BI dashboarding,
data quality testing, learning analytics, and responsible design for
AI-assisted insight generation.
