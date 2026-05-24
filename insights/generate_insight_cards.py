"""Generate governed aggregate insight cards from approved dbt marts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


APPROVED_MART_TABLES = frozenset(
    {
        "mart_student_success_features",
        "fct_course_engagement_daily",
        "fct_assessment_performance",
    }
)
RISK_BAND_ORDER = ("Low", "Medium", "High")


def get_project_root() -> Path:
    """Resolve the project root relative to this script."""
    return Path(__file__).resolve().parents[1]


def utc_timestamp() -> str:
    """Return an ISO timestamp in UTC."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_project_path(project_root: Path, path_value: str) -> Path:
    """Resolve a CLI path relative to the project root when needed."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_root / path


def load_approved_mart(connection: duckdb.DuckDBPyConnection, table_name: str):
    """Load only explicitly approved dbt mart tables."""
    if table_name not in APPROVED_MART_TABLES:
        allowed = ", ".join(sorted(APPROVED_MART_TABLES))
        raise ValueError(
            f"Table '{table_name}' is not approved for insight-card generation. "
            f"Allowed tables: {allowed}."
        )

    try:
        return connection.execute(f'select * from "{table_name}"').fetchdf()
    except duckdb.Error as exc:
        raise RuntimeError(
            f"Approved mart table '{table_name}' could not be loaded. "
            "Run the local ingestion and dbt pipeline before generating cards."
        ) from exc


def require_columns(data_frame: pd.DataFrame, columns: set[str], table_name: str):
    """Fail clearly when an approved mart is missing expected columns."""
    missing_columns = sorted(columns.difference(data_frame.columns))
    if missing_columns:
        raise ValueError(
            f"Approved mart '{table_name}' is missing expected columns: "
            f"{', '.join(missing_columns)}."
        )


def normalize_bool_value(value):
    """Normalize boolean-like mart values for aggregate calculations."""
    if pd.isna(value):
        return pd.NA
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def percent(value: float | int) -> float:
    """Round a percentage for JSON output."""
    return round(float(value), 2)


def make_card(
    title: str,
    metric_name: str,
    observation: str,
    supporting_values: dict,
    interpretation: str,
    limitations: str,
):
    """Create one insight card using the governed schema."""
    return {
        "title": title,
        "metric_name": metric_name,
        "population_scope": ("All student-module attempts in approved dbt mart tables"),
        "time_or_course_scope": "All available OULAD module presentations",
        "observation": observation,
        "supporting_values": supporting_values,
        "interpretation": interpretation,
        "limitations": limitations,
        "generated_at": utc_timestamp(),
    }


def build_overall_success_cards(success_features: pd.DataFrame) -> list[dict]:
    """Build cards for overall student-success risk indicators."""
    table_name = "mart_student_success_features"
    require_columns(success_features, {"risk_band", "is_withdrawn"}, table_name)
    if success_features.empty:
        return []

    chart_data = success_features[["risk_band", "is_withdrawn"]].copy()
    chart_data["withdrawn_flag"] = chart_data["is_withdrawn"].map(normalize_bool_value)
    chart_data = chart_data.dropna(subset=["risk_band", "withdrawn_flag"])
    if chart_data.empty:
        return []

    chart_data["withdrawn_flag"] = chart_data["withdrawn_flag"].astype(bool)
    grouped = (
        chart_data.groupby("risk_band", observed=True)
        .agg(students=("risk_band", "size"), withdrawal_rate=("withdrawn_flag", "mean"))
        .reset_index()
    )
    grouped["withdrawal_rate"] = grouped["withdrawal_rate"] * 100

    supporting_values = {}
    for risk_band in RISK_BAND_ORDER:
        row = grouped[grouped["risk_band"] == risk_band]
        if not row.empty:
            supporting_values[risk_band] = {
                "students": int(row["students"].iloc[0]),
                "withdrawal_rate": percent(row["withdrawal_rate"].iloc[0]),
            }

    if "High" in supporting_values:
        observation = (
            "High rule-based risk students have a withdrawal rate of "
            f"{supporting_values['High']['withdrawal_rate']}% across "
            f"{supporting_values['High']['students']:,} student-module attempts."
        )
    else:
        observation = (
            "Withdrawal rates were calculated for the available rule-based risk bands."
        )

    return [
        make_card(
            title="Withdrawal rate by rule-based risk band",
            metric_name="withdrawal_rate_by_risk_band",
            observation=observation,
            supporting_values=supporting_values,
            interpretation=(
                "Risk bands can support monitoring and prioritization, but they "
                "are deterministic rule-based analytical indicators."
            ),
            limitations="Risk bands are not validated predictive ML outputs.",
        )
    ]


def build_engagement_cards(success_features: pd.DataFrame) -> list[dict]:
    """Build cards for engagement-related student-success indicators."""
    table_name = "mart_student_success_features"
    require_columns(
        success_features,
        {
            "has_declining_engagement",
            "is_withdrawn",
            "is_low_engagement",
            "average_score",
        },
        table_name,
    )
    if success_features.empty:
        return []

    cards = []

    decline_data = success_features[["has_declining_engagement", "is_withdrawn"]].copy()
    decline_data["declining_engagement"] = decline_data["has_declining_engagement"].map(
        normalize_bool_value
    )
    decline_data["withdrawn_flag"] = decline_data["is_withdrawn"].map(
        normalize_bool_value
    )
    decline_data = decline_data.dropna(
        subset=["declining_engagement", "withdrawn_flag"]
    )

    if not decline_data.empty:
        decline_data["declining_engagement"] = decline_data[
            "declining_engagement"
        ].astype(bool)
        decline_data["withdrawn_flag"] = decline_data["withdrawn_flag"].astype(bool)
        grouped = (
            decline_data.groupby("declining_engagement", observed=True)
            .agg(
                students=("declining_engagement", "size"),
                withdrawal_rate=("withdrawn_flag", "mean"),
            )
            .reset_index()
        )
        grouped["withdrawal_rate"] = grouped["withdrawal_rate"] * 100

        supporting_values = {}
        labels = {
            False: "No declining engagement",
            True: "Declining engagement",
        }
        for flag, label in labels.items():
            row = grouped[grouped["declining_engagement"] == flag]
            if not row.empty:
                supporting_values[label] = {
                    "students": int(row["students"].iloc[0]),
                    "withdrawal_rate": percent(row["withdrawal_rate"].iloc[0]),
                }

        observation = (
            "Withdrawal rates were calculated for students with and without "
            "declining engagement within their observed activity windows."
        )
        if set(labels.values()).issubset(supporting_values):
            observation = (
                "Students with declining engagement have a withdrawal rate of "
                f"{supporting_values['Declining engagement']['withdrawal_rate']}%, "
                "compared with "
                f"{supporting_values['No declining engagement']['withdrawal_rate']}% "
                "for students without declining engagement."
            )

        cards.append(
            make_card(
                title="Withdrawal rate by declining engagement",
                metric_name="withdrawal_rate_by_declining_engagement",
                observation=observation,
                supporting_values=supporting_values,
                interpretation=(
                    "Declining engagement can help course teams monitor changing "
                    "student activity patterns."
                ),
                limitations=(
                    "Declining engagement is measured only within each student's "
                    "observed activity window and does not establish causality."
                ),
            )
        )

    score_data = success_features[["is_low_engagement", "average_score"]].copy()
    score_data["low_engagement"] = score_data["is_low_engagement"].map(
        normalize_bool_value
    )
    score_data["average_score"] = pd.to_numeric(
        score_data["average_score"],
        errors="coerce",
    )
    score_data = score_data.dropna(subset=["low_engagement", "average_score"])

    if not score_data.empty:
        score_data["low_engagement"] = score_data["low_engagement"].astype(bool)
        grouped = (
            score_data.groupby("low_engagement", observed=True)
            .agg(
                students=("low_engagement", "size"),
                average_score=("average_score", "mean"),
            )
            .reset_index()
        )

        supporting_values = {}
        labels = {
            False: "Not low engagement",
            True: "Low engagement",
        }
        for flag, label in labels.items():
            row = grouped[grouped["low_engagement"] == flag]
            if not row.empty:
                supporting_values[label] = {
                    "students": int(row["students"].iloc[0]),
                    "average_score": percent(row["average_score"].iloc[0]),
                }

        observation = (
            "Average assessment scores were calculated for low-engagement and "
            "non-low-engagement students where scores are available."
        )
        if set(labels.values()).issubset(supporting_values):
            observation = (
                "Low-engagement students have an average score of "
                f"{supporting_values['Low engagement']['average_score']}, compared "
                "with "
                f"{supporting_values['Not low engagement']['average_score']} for "
                "students who are not low engagement."
            )

        cards.append(
            make_card(
                title="Average score by engagement group",
                metric_name="average_score_by_low_engagement",
                observation=observation,
                supporting_values=supporting_values,
                interpretation=(
                    "Engagement-group score comparisons can guide descriptive "
                    "course monitoring and follow-up analysis."
                ),
                limitations=(
                    "This aggregate comparison is descriptive and does not prove "
                    "that engagement caused the score difference."
                ),
            )
        )

    return cards


def build_assessment_cards(assessment_performance: pd.DataFrame) -> list[dict]:
    """Build cards from approved assessment performance marts."""
    table_name = "fct_assessment_performance"
    require_columns(
        assessment_performance,
        {"assessment_type", "average_score", "submitted_assessments"},
        table_name,
    )
    if assessment_performance.empty:
        return []

    chart_data = assessment_performance[
        ["assessment_type", "average_score", "submitted_assessments"]
    ].copy()
    chart_data["average_score"] = pd.to_numeric(
        chart_data["average_score"],
        errors="coerce",
    )
    chart_data["submitted_assessments"] = pd.to_numeric(
        chart_data["submitted_assessments"],
        errors="coerce",
    )
    chart_data = chart_data.dropna(
        subset=["assessment_type", "average_score", "submitted_assessments"]
    )
    chart_data = chart_data[chart_data["submitted_assessments"] > 0]
    if chart_data.empty:
        return []

    grouped_rows = []
    for assessment_type, group in chart_data.groupby("assessment_type", observed=True):
        submission_count = int(group["submitted_assessments"].sum())
        weighted_score = (
            group["average_score"] * group["submitted_assessments"]
        ).sum() / submission_count
        grouped_rows.append(
            {
                "assessment_type": assessment_type,
                "submitted_assessments": submission_count,
                "average_score": percent(weighted_score),
            }
        )

    supporting_values = {
        row["assessment_type"]: {
            "submitted_assessments": row["submitted_assessments"],
            "average_score": row["average_score"],
        }
        for row in sorted(grouped_rows, key=lambda item: item["assessment_type"])
    }

    return [
        make_card(
            title="Average assessment score by assessment type",
            metric_name="average_score_by_assessment_type",
            observation=(
                "Average scores were calculated by assessment type using "
                "submission-weighted assessment performance marts."
            ),
            supporting_values=supporting_values,
            interpretation=(
                "Assessment-type score patterns can help identify where course "
                "teams may want to review assessment design or support."
            ),
            limitations=(
                "Scores are aggregate mart metrics and do not include row-level "
                "student submissions."
            ),
        )
    ]


def build_learning_journey_cards(success_features: pd.DataFrame) -> list[dict]:
    """Build cards for aggregate learning journey funnel counts."""
    table_name = "mart_student_success_features"
    require_columns(
        success_features,
        {"total_clicks", "submitted_assessments", "final_result"},
        table_name,
    )
    if success_features.empty:
        return []

    total_clicks = pd.to_numeric(success_features["total_clicks"], errors="coerce")
    submitted_assessments = pd.to_numeric(
        success_features["submitted_assessments"],
        errors="coerce",
    )
    enrolled_students = len(success_features)
    active_students = int((total_clicks.fillna(0) > 0).sum())
    submitted_students = int((submitted_assessments.fillna(0) > 0).sum())
    passed_students = int(
        success_features["final_result"].isin(["Pass", "Distinction"]).sum()
    )

    supporting_values = {
        "enrolled_students": enrolled_students,
        "active_in_vle": active_students,
        "submitted_assessment": submitted_students,
        "passed_or_distinction": passed_students,
    }

    return [
        make_card(
            title="Learning journey funnel counts",
            metric_name="learning_journey_funnel_counts",
            observation=(
                f"Of {enrolled_students:,} enrolled student-module attempts, "
                f"{active_students:,} were active in the VLE, "
                f"{submitted_students:,} submitted at least one assessment, and "
                f"{passed_students:,} achieved Pass or Distinction."
            ),
            supporting_values=supporting_values,
            interpretation=(
                "The funnel provides a compact aggregate view of learner progress "
                "through engagement, assessment submission, and successful outcome."
            ),
            limitations=(
                "The funnel is descriptive and based on approved mart aggregates; "
                "it does not model causal progression."
            ),
        )
    ]


def write_insight_cards(cards: list[dict], output_path: Path) -> None:
    """Write generated cards to a local runtime JSON artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cards, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate deterministic aggregate insight cards from approved dbt marts."
        )
    )
    parser.add_argument(
        "--duckdb-path",
        default="data/warehouse/laip.duckdb",
        help="Path to the local DuckDB warehouse.",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/insight_cards.json",
        help="Path for the generated insight-card JSON artifact.",
    )
    return parser.parse_args()


def main() -> None:
    """Generate governed aggregate insight cards."""
    args = parse_args()
    project_root = get_project_root()
    duckdb_path = resolve_project_path(project_root, args.duckdb_path)
    output_path = resolve_project_path(project_root, args.output_path)

    if not duckdb_path.exists():
        raise SystemExit(
            f"DuckDB warehouse not found at {duckdb_path}. Run the local "
            "ingestion and dbt pipeline before generating insight cards."
        )

    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        success_features = load_approved_mart(
            connection,
            "mart_student_success_features",
        )
        assessment_performance = load_approved_mart(
            connection,
            "fct_assessment_performance",
        )

    cards = []
    cards.extend(build_overall_success_cards(success_features))
    cards.extend(build_engagement_cards(success_features))
    cards.extend(build_learning_journey_cards(success_features))
    cards.extend(build_assessment_cards(assessment_performance))

    write_insight_cards(cards, output_path)
    print(f"Wrote {len(cards)} governed aggregate insight cards to {output_path}")


if __name__ == "__main__":
    main()
