"""Load expected OULAD raw CSV files into DuckDB raw tables."""

from pathlib import Path

import duckdb


INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse" / "laip.duckdb"

RAW_TABLES = {
    "courses.csv": "raw_courses",
    "assessments.csv": "raw_assessments",
    "vle.csv": "raw_vle",
    "studentInfo.csv": "raw_student_info",
    "studentRegistration.csv": "raw_student_registration",
    "studentAssessment.csv": "raw_student_assessment",
    "studentVle.csv": "raw_student_vle",
}


def load_csv(
    connection: duckdb.DuckDBPyConnection,
    csv_path: Path,
    table_name: str,
) -> int:
    """Replace a raw table with data loaded directly from a CSV file."""
    connection.execute(f"DROP TABLE IF EXISTS {table_name}")
    connection.execute(
        f"""
        CREATE TABLE {table_name} AS
        SELECT *
        FROM read_csv_auto(?, header = true)
        """,
        [str(csv_path)],
    )
    row_count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    return int(row_count)


def main() -> int:
    """Load all expected OULAD raw CSV files into the local DuckDB warehouse."""
    missing_files = [
        filename for filename in RAW_TABLES if not (RAW_DATA_DIR / filename).exists()
    ]

    print(f"Loading OULAD raw CSV files from {RAW_DATA_DIR}")
    print(f"Target DuckDB warehouse: {WAREHOUSE_PATH}")

    if missing_files:
        for filename in missing_files:
            print(f"FAIL {filename}: missing file")
        print(f"Load failed: {len(missing_files)} missing file(s)")
        return 1

    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)

    issue_count = 0
    connection = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        for filename, table_name in RAW_TABLES.items():
            csv_path = RAW_DATA_DIR / filename
            try:
                row_count = load_csv(connection, csv_path, table_name)
            except duckdb.Error as exc:
                print(f"FAIL {filename} -> {table_name}: {exc}")
                issue_count += 1
                continue

            print(f"OK   {filename} -> {table_name}: {row_count} rows")
    finally:
        connection.close()

    if issue_count:
        print(f"Load failed: {issue_count} issue(s)")
        return 1

    print("Load passed: all raw tables loaded successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
