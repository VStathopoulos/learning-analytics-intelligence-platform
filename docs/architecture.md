# Architecture

Early architecture notes for the Learning Analytics Intelligence Platform.

## 1. Purpose

The platform supports analytics engineering, BI reporting, and later controlled
LLM-assisted insight generation for online learning analytics using the Open
University Learning Analytics Dataset (OULAD).

The initial goal is to build a reliable local pipeline before adding production
orchestration or advanced insight automation.

## 2. High-Level Data Flow

OULAD raw files are loaded by Python ingestion code into a local DuckDB
warehouse at `data/warehouse/laip.duckdb`. dbt-duckdb transforms the warehouse
tables into staging, intermediate, and mart models. Dash/Plotly reads curated
mart outputs for interactive analysis. A later LLM insight layer will generate
aggregate-only narrative cards from approved mart-level data.

## 3. Main Layers

- Raw data: OULAD source files placed under `data/raw/`.
- Ingestion: Python code validates and loads raw files into DuckDB.
- Warehouse: DuckDB stores local analytical tables at `data/warehouse/laip.duckdb`.
- Transformations: dbt-duckdb organizes models into staging, intermediate, and
  marts.
- Dashboard: Dash/Plotly presents curated analytics from dbt marts.
- LLM insights: Later-stage generators produce controlled insight cards from
  aggregate mart outputs only.

## 4. Data Governance Rule For LLM Insights

The LLM must not read raw student-level records. LLM insight generation is
limited to approved aggregate dbt marts and documented outputs suitable for
summary-level interpretation.

## 5. Deferred Components

- Airflow orchestration is deferred until the manual pipeline works reliably.
- LLM insight generation is deferred until dbt marts and dashboard needs are
  clearly defined.
- Production deployment, monitoring, and access controls are outside the initial
  local architecture.

## 6. Initial Architecture Diagram

```text
OULAD raw files
    ->
Python ingestion
    ->
DuckDB at data/warehouse/laip.duckdb
    ->
dbt staging/intermediate/marts
    ->
Dash dashboard
    ->
aggregate-only LLM insight cards
```
