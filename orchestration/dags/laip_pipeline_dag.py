"""Airflow DAG for the Learning Analytics Intelligence Platform pipeline."""

from __future__ import annotations

import os
import shlex
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator


DEFAULT_PROJECT_ROOT = "/opt/airflow/learning-analytics-intelligence-platform"
PROJECT_ROOT = os.environ.get("LAIP_PROJECT_ROOT", DEFAULT_PROJECT_ROOT)


def project_command(command: str) -> str:
    """Run a shell command from the configured project root."""
    return f"cd {shlex.quote(PROJECT_ROOT)} && {command}"


with DAG(
    dag_id="laip_learning_analytics_pipeline",
    description=(
        "Orchestrates raw validation, DuckDB loading, dbt model build, and dbt "
        "tests for the Learning Analytics Intelligence Platform."
    ),
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["learning-analytics", "duckdb", "dbt", "portfolio"],
) as dag:
    # Raw OULAD CSV files and the DuckDB warehouse are local runtime artifacts
    # that are intentionally ignored by Git. This DAG orchestrates the existing
    # local pipeline but does not launch the separate Dash dashboard.
    validate_raw_oulad_data = BashOperator(
        task_id="validate_raw_oulad_data",
        bash_command=project_command("python ingestion/validate_raw_data.py"),
    )

    load_raw_oulad_to_duckdb = BashOperator(
        task_id="load_raw_oulad_to_duckdb",
        bash_command=project_command("python ingestion/load_raw_to_duckdb.py"),
    )

    run_dbt_models = BashOperator(
        task_id="run_dbt_models",
        bash_command=project_command("cd dbt && dbt run --profiles-dir ."),
    )

    test_dbt_models = BashOperator(
        task_id="test_dbt_models",
        bash_command=project_command("cd dbt && dbt test --profiles-dir ."),
    )

    (
        validate_raw_oulad_data
        >> load_raw_oulad_to_duckdb
        >> run_dbt_models
        >> test_dbt_models
    )
