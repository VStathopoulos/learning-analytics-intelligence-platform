"""Validate expected OULAD raw CSV file headers."""

import csv
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INGESTION_DIR.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

EXPECTED_SCHEMAS = {
    "courses.csv": [
        "code_module",
        "code_presentation",
        "module_presentation_length",
    ],
    "assessments.csv": [
        "code_module",
        "code_presentation",
        "id_assessment",
        "assessment_type",
        "date",
        "weight",
    ],
    "vle.csv": [
        "id_site",
        "code_module",
        "code_presentation",
        "activity_type",
        "week_from",
        "week_to",
    ],
    "studentInfo.csv": [
        "code_module",
        "code_presentation",
        "id_student",
        "gender",
        "region",
        "highest_education",
        "imd_band",
        "age_band",
        "num_of_prev_attempts",
        "studied_credits",
        "disability",
        "final_result",
    ],
    "studentRegistration.csv": [
        "code_module",
        "code_presentation",
        "id_student",
        "date_registration",
        "date_unregistration",
    ],
    "studentAssessment.csv": [
        "id_assessment",
        "id_student",
        "date_submitted",
        "is_banked",
        "score",
    ],
    "studentVle.csv": [
        "code_module",
        "code_presentation",
        "id_student",
        "id_site",
        "date",
        "sum_click",
    ],
}


def read_header(csv_path: Path) -> list[str]:
    """Read only the header row from a CSV file."""
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        return next(reader, [])


def main() -> int:
    """Validate expected raw CSV files and headers."""
    issue_count = 0

    print(f"Validating OULAD raw CSV headers in {RAW_DATA_DIR}")

    for filename, expected_columns in EXPECTED_SCHEMAS.items():
        csv_path = RAW_DATA_DIR / filename

        if not csv_path.exists():
            print(f"FAIL {filename}: missing file")
            issue_count += 1
            continue

        actual_columns = read_header(csv_path)
        if actual_columns != expected_columns:
            print(f"FAIL {filename}: unexpected columns")
            print(f"  expected: {', '.join(expected_columns)}")
            print(f"  actual:   {', '.join(actual_columns)}")
            issue_count += 1
            continue

        print(f"OK   {filename}")

    if issue_count:
        print(f"Validation failed: {issue_count} issue(s)")
        return 1

    print("Validation passed: all expected files and columns are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
