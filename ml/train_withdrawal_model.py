"""Train leakage-safe day-30 withdrawal prediction models."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SOURCE_TABLE = "mart_withdrawal_prediction_features"
LOGISTIC_REGRESSION_MODEL_VERSION = "logistic_regression_day30_v1"
RANDOM_FOREST_MODEL_VERSION = "random_forest_day30_v1"
TARGET_COLUMN = "withdraw_after_day_30"
MISSING_CATEGORY = "__missing__"
SPLIT_STRATEGY = (
    "Train on presentations before the latest; test on latest presentation."
)
SERVING_TABLES = {
    "predictions": "ml_withdrawal_predictions",
    "metrics": "ml_withdrawal_metrics",
    "feature_importance": "ml_withdrawal_feature_importance",
    "model_comparison": "ml_withdrawal_model_comparison",
    "roc_curve": "ml_withdrawal_roc_curve",
    "pr_curve": "ml_withdrawal_pr_curve",
}
IDENTIFIER_COLUMNS = [
    "code_module",
    "code_presentation",
    "id_student",
    "prediction_day",
]
REQUIRED_COLUMNS = set(IDENTIFIER_COLUMNS + [TARGET_COLUMN])
EXCLUDED_FEATURE_COLUMNS = {
    "code_module",
    "code_presentation",
    "id_student",
    "prediction_day",
    "withdraw_after_day_30",
    "final_result",
    "date_unregistration",
    "risk_band",
    "risk_score_simple",
    "is_withdrawn",
    "has_declining_engagement",
    "total_clicks",
    "average_score",
}
PREDICTION_COLUMNS = [
    "code_module",
    "code_presentation",
    "id_student",
    "prediction_day",
    "split",
    "withdraw_after_day_30",
    "predicted_withdrawal_probability",
    "predicted_risk_band",
    "model_version",
]
FEATURE_IMPORTANCE_COLUMNS = [
    "feature",
    "importance_type",
    "importance_value",
    "abs_importance_value",
    "model_version",
]
ROC_CURVE_COLUMNS = [
    "model_type",
    "model_version",
    "split",
    "threshold",
    "false_positive_rate",
    "true_positive_rate",
]
PR_CURVE_COLUMNS = [
    "model_type",
    "model_version",
    "split",
    "threshold",
    "precision",
    "recall",
]
MODEL_COMPARISON_COLUMNS = [
    "model_type",
    "model_version",
    "selected_model",
    "roc_auc",
    "average_precision",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "true_negative",
    "false_positive",
    "false_negative",
    "true_positive",
    "train_rows",
    "test_rows",
    "positive_rate_train",
    "positive_rate_test",
    "prediction_day",
    "target",
    "generated_at",
    "split_strategy",
    "selection_reason",
]


@dataclass(frozen=True)
class ModelSpec:
    """Configuration for one withdrawal prediction model candidate."""

    model_type: str
    model_version: str
    estimator: object
    scale_numeric: bool
    importance_type: str


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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Train leakage-safe Logistic Regression and Random Forest models "
            "for day-30 withdrawal prediction."
        )
    )
    parser.add_argument(
        "--duckdb-path",
        default="data/warehouse/laip.duckdb",
        help="Path to the local DuckDB warehouse.",
    )
    parser.add_argument(
        "--predictions-output",
        default="data/processed/ml_withdrawal_predictions.csv",
        help="Path for scored withdrawal predictions from the selected model.",
    )
    parser.add_argument(
        "--metrics-output",
        default="data/processed/ml_withdrawal_metrics.json",
        help="Path for selected model evaluation metrics.",
    )
    parser.add_argument(
        "--feature-importance-output",
        default="data/processed/ml_withdrawal_feature_importance.csv",
        help="Path for selected model feature importance.",
    )
    parser.add_argument(
        "--model-comparison-output",
        default="data/processed/ml_withdrawal_model_comparison.csv",
        help="Path for held-out metric comparison across model candidates.",
    )
    parser.add_argument(
        "--roc-curve-output",
        default="data/processed/ml_withdrawal_roc_curve.csv",
        help="Path for selected model held-out ROC curve points.",
    )
    parser.add_argument(
        "--pr-curve-output",
        default="data/processed/ml_withdrawal_pr_curve.csv",
        help="Path for selected model held-out Precision-Recall curve points.",
    )
    return parser.parse_args()


def get_model_specs() -> list[ModelSpec]:
    """Build the baseline and challenger model configurations."""
    return [
        ModelSpec(
            model_type="LogisticRegression",
            model_version=LOGISTIC_REGRESSION_MODEL_VERSION,
            estimator=LogisticRegression(max_iter=1000, class_weight="balanced"),
            scale_numeric=True,
            importance_type="coefficient",
        ),
        ModelSpec(
            model_type="RandomForestClassifier",
            model_version=RANDOM_FOREST_MODEL_VERSION,
            estimator=RandomForestClassifier(
                n_estimators=300,
                min_samples_leaf=10,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
            scale_numeric=False,
            importance_type="gini_importance",
        ),
    ]


def load_feature_mart(duckdb_path: Path) -> pd.DataFrame:
    """Load the approved leakage-safe withdrawal prediction mart."""
    if not duckdb_path.exists():
        raise FileNotFoundError(
            f"DuckDB warehouse not found at {duckdb_path}. Run ingestion and dbt "
            "before training withdrawal prediction models."
        )

    try:
        with duckdb.connect(str(duckdb_path), read_only=True) as connection:
            return connection.execute(f"select * from {SOURCE_TABLE}").fetchdf()
    except duckdb.Error as exc:
        raise RuntimeError(
            f"Could not load {SOURCE_TABLE} from DuckDB. Run dbt before training "
            "withdrawal prediction models."
        ) from exc


def require_columns(data_frame: pd.DataFrame) -> None:
    """Validate required training columns are present."""
    missing_columns = sorted(REQUIRED_COLUMNS.difference(data_frame.columns))
    if missing_columns:
        raise ValueError(
            "Withdrawal prediction mart is missing required columns: "
            f"{', '.join(missing_columns)}."
        )


def target_to_binary(target: pd.Series) -> pd.Series:
    """Convert boolean-like target values to binary integers."""
    if pd.api.types.is_bool_dtype(target):
        return target.astype(int)

    if pd.api.types.is_numeric_dtype(target):
        return target.astype(int)

    normalized = target.astype(str).str.strip().str.lower()
    mapped = normalized.map({"true": 1, "1": 1, "false": 0, "0": 0})
    if mapped.isna().any():
        raise ValueError(
            "Target column contains values that cannot be converted to 0/1."
        )
    return mapped.astype(int)


def assign_temporal_split(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Hold out the latest course presentation for testing."""
    if data_frame["code_presentation"].isna().any():
        raise ValueError("code_presentation contains null values; cannot split safely.")

    presentations = sorted(data_frame["code_presentation"].unique())
    if len(presentations) < 2:
        raise ValueError(
            "At least two code_presentation values are required for a temporal split."
        )

    latest_presentation = presentations[-1]
    split_data = data_frame.copy()
    split_data["split"] = "train"
    split_data.loc[
        split_data["code_presentation"] == latest_presentation,
        "split",
    ] = "test"

    if split_data[split_data["split"] == "train"].empty:
        raise ValueError("Temporal split produced no training rows.")
    if split_data[split_data["split"] == "test"].empty:
        raise ValueError("Temporal split produced no test rows.")

    return split_data


def select_feature_columns(data_frame: pd.DataFrame) -> list[str]:
    """Select model feature columns after applying the governance exclusion list."""
    feature_columns = [
        column
        for column in data_frame.columns
        if column not in EXCLUDED_FEATURE_COLUMNS
    ]
    feature_columns = [column for column in feature_columns if column != "split"]
    if not feature_columns:
        raise ValueError("No feature columns remain after applying exclusions.")
    return feature_columns


def split_feature_types(
    data_frame: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[list[str], list[str]]:
    """Separate numeric and categorical feature columns."""
    numeric_columns = []
    categorical_columns = []

    for column in feature_columns:
        dtype = data_frame[column].dtype
        if pd.api.types.is_bool_dtype(dtype):
            categorical_columns.append(column)
        elif pd.api.types.is_numeric_dtype(dtype):
            numeric_columns.append(column)
        else:
            categorical_columns.append(column)

    return numeric_columns, categorical_columns


def prepare_categorical_features(
    data_frame: pd.DataFrame,
    categorical_columns: list[str],
) -> pd.DataFrame:
    """Prepare categorical values for robust sklearn preprocessing."""
    prepared = data_frame.copy()
    for column in categorical_columns:
        prepared[column] = (
            prepared[column]
            .astype("object")
            .where(prepared[column].notna(), MISSING_CATEGORY)
            .astype(str)
        )
    return prepared


def make_one_hot_encoder() -> OneHotEncoder:
    """Create a OneHotEncoder compatible with common scikit-learn versions."""
    encoder_kwargs = {"handle_unknown": "ignore"}
    if "sparse_output" in signature(OneHotEncoder).parameters:
        encoder_kwargs["sparse_output"] = False
    else:
        encoder_kwargs["sparse"] = False
    return OneHotEncoder(**encoder_kwargs)


def build_numeric_pipeline(scale_numeric: bool) -> Pipeline:
    """Build numeric preprocessing for the candidate model."""
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        steps.append(("scaler", StandardScaler()))
    return Pipeline(steps=steps)


def build_model_pipeline(
    numeric_columns: list[str],
    categorical_columns: list[str],
    spec: ModelSpec,
) -> Pipeline:
    """Build preprocessing and estimator steps for a model candidate."""
    transformers = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                build_numeric_pipeline(spec.scale_numeric),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    steps=[
                        (
                            "imputer",
                            SimpleImputer(
                                strategy="constant",
                                fill_value=MISSING_CATEGORY,
                            ),
                        ),
                        ("one_hot", make_one_hot_encoder()),
                    ]
                ),
                categorical_columns,
            )
        )

    if not transformers:
        raise ValueError("No numeric or categorical feature columns were found.")

    preprocessor = ColumnTransformer(transformers=transformers)
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", spec.estimator),
        ]
    )


def probability_to_risk_band(probability: float) -> str:
    """Convert a withdrawal probability to a dashboard-friendly risk band."""
    if probability < 0.33:
        return "Low"
    if probability < 0.66:
        return "Medium"
    return "High"


def safe_roc_auc(
    y_true: pd.Series, y_score: pd.Series
) -> tuple[float | None, str | None]:
    """Compute ROC AUC when both target classes are present."""
    if y_true.nunique() < 2:
        return None, "ROC AUC was not computed because the test split has one class."
    return float(roc_auc_score(y_true, y_score)), None


def safe_average_precision(
    y_true: pd.Series, y_score: pd.Series
) -> tuple[float | None, str | None]:
    """Compute average precision when both target classes are present."""
    if y_true.nunique() < 2:
        return (
            None,
            "Average precision was not computed because the test split has one class.",
        )
    return float(average_precision_score(y_true, y_score)), None


def build_metrics(
    spec: ModelSpec,
    y_train: pd.Series,
    y_test: pd.Series,
    y_pred: pd.Series,
    y_probability: pd.Series,
    prediction_day: int,
    generated_at: str,
    warnings: list[str],
) -> dict:
    """Build model evaluation metrics for the held-out presentation."""
    roc_auc, roc_auc_warning = safe_roc_auc(y_test, y_probability)
    if roc_auc_warning:
        warnings.append(roc_auc_warning)
    average_precision, average_precision_warning = safe_average_precision(
        y_test,
        y_probability,
    )
    if average_precision_warning:
        warnings.append(average_precision_warning)

    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        y_test,
        y_pred,
        labels=[0, 1],
    ).ravel()

    return {
        "model_type": spec.model_type,
        "model_version": spec.model_version,
        "target": TARGET_COLUMN,
        "prediction_day": prediction_day,
        "split_strategy": SPLIT_STRATEGY,
        "generated_at": generated_at,
        "train_rows": int(len(y_train)),
        "test_rows": int(len(y_test)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "true_negative": int(true_negative),
        "false_positive": int(false_positive),
        "false_negative": int(false_negative),
        "true_positive": int(true_positive),
        "warnings": warnings,
    }


def fit_and_evaluate_model(
    spec: ModelSpec,
    numeric_columns: list[str],
    categorical_columns: list[str],
    feature_columns: list[str],
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    data: pd.DataFrame,
    prediction_day: int,
    generated_at: str,
) -> dict:
    """Train one model candidate and evaluate it on the held-out split."""
    model = build_model_pipeline(numeric_columns, categorical_columns, spec)
    x_train = train_data[feature_columns]
    y_train = train_data[TARGET_COLUMN]
    x_test = test_data[feature_columns]
    y_test = test_data[TARGET_COLUMN]

    model.fit(x_train, y_train)

    test_probabilities = pd.Series(
        model.predict_proba(x_test)[:, 1],
        index=test_data.index,
    )
    test_predictions = pd.Series(model.predict(x_test), index=test_data.index)
    all_probabilities = pd.Series(
        model.predict_proba(data[feature_columns])[:, 1],
        index=data.index,
    )

    warnings = []
    metrics = build_metrics(
        spec=spec,
        y_train=y_train,
        y_test=y_test,
        y_pred=test_predictions,
        y_probability=test_probabilities,
        prediction_day=prediction_day,
        generated_at=generated_at,
        warnings=warnings,
    )
    return {
        "spec": spec,
        "model": model,
        "metrics": metrics,
        "y_test": y_test,
        "test_probabilities": test_probabilities,
        "all_probabilities": all_probabilities,
    }


def roc_auc_sort_value(roc_auc: float | None) -> float:
    """Return a sortable ROC AUC value with nulls ranked last."""
    if roc_auc is None or pd.isna(roc_auc):
        return float("-inf")
    return float(roc_auc)


def is_roc_auc_tie(left: float | None, right: float | None) -> bool:
    """Check exact ROC AUC ties, treating two null values as tied."""
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return float(left) == float(right)


def select_best_model(results: list[dict]) -> dict:
    """Select the best model by held-out ROC AUC, preferring LR in ties."""
    return max(
        results,
        key=lambda result: (
            roc_auc_sort_value(result["metrics"]["roc_auc"]),
            result["spec"].model_type == "LogisticRegression",
        ),
    )


def build_selection_reason(selected_result: dict, results: list[dict]) -> str:
    """Describe why the selected model was chosen."""
    selected_auc = selected_result["metrics"]["roc_auc"]
    selected_model_type = selected_result["spec"].model_type
    tied_for_best = any(
        result is not selected_result
        and is_roc_auc_tie(selected_auc, result["metrics"]["roc_auc"])
        for result in results
    )

    if selected_auc is None:
        return (
            f"Selected {selected_model_type} because all held-out ROC AUC values "
            "were null; Logistic Regression is preferred in ties."
        )
    if tied_for_best:
        return (
            f"Selected {selected_model_type} because it tied for best held-out "
            f"ROC AUC ({selected_auc:.6f}); Logistic Regression is preferred in ties."
        )
    return (
        f"Selected {selected_model_type} because it had the highest held-out "
        f"ROC AUC ({selected_auc:.6f})."
    )


def build_predictions(
    data_frame: pd.DataFrame,
    probabilities: pd.Series,
    model_version: str,
) -> pd.DataFrame:
    """Build the dashboard-ready prediction output."""
    predictions = data_frame[
        [
            "code_module",
            "code_presentation",
            "id_student",
            "prediction_day",
            "split",
            TARGET_COLUMN,
        ]
    ].copy()
    predictions[TARGET_COLUMN] = target_to_binary(predictions[TARGET_COLUMN])
    predictions["predicted_withdrawal_probability"] = probabilities.round(6)
    predictions["predicted_risk_band"] = predictions[
        "predicted_withdrawal_probability"
    ].map(probability_to_risk_band)
    predictions["model_version"] = model_version
    return predictions[PREDICTION_COLUMNS]


def empty_feature_importance_frame() -> pd.DataFrame:
    """Return an empty feature importance frame with stable column dtypes."""
    return pd.DataFrame(
        {
            "feature": pd.Series(dtype="str"),
            "importance_type": pd.Series(dtype="str"),
            "importance_value": pd.Series(dtype="float64"),
            "abs_importance_value": pd.Series(dtype="float64"),
            "model_version": pd.Series(dtype="str"),
        }
    )


def extract_feature_importance(
    model: Pipeline,
    spec: ModelSpec,
    warnings: list[str],
) -> pd.DataFrame:
    """Extract transformed feature importance from the selected model."""
    try:
        feature_names = model.named_steps["preprocessor"].get_feature_names_out()
        estimator = model.named_steps["model"]
        if spec.importance_type == "coefficient":
            importance_values = estimator.coef_[0]
        elif spec.importance_type == "gini_importance":
            importance_values = estimator.feature_importances_
        else:
            raise ValueError(f"Unsupported importance type: {spec.importance_type}")
    except (AttributeError, KeyError, IndexError, ValueError) as exc:
        warnings.append(f"Feature importance could not be extracted: {exc}")
        return empty_feature_importance_frame()

    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "importance_type": spec.importance_type,
            "importance_value": importance_values,
        }
    )
    importance["abs_importance_value"] = importance["importance_value"].abs()
    importance["model_version"] = spec.model_version
    return importance.sort_values("abs_importance_value", ascending=False)[
        FEATURE_IMPORTANCE_COLUMNS
    ]


def empty_roc_curve_frame() -> pd.DataFrame:
    """Return an empty ROC curve frame with stable column dtypes."""
    return pd.DataFrame(
        {
            "model_type": pd.Series(dtype="str"),
            "model_version": pd.Series(dtype="str"),
            "split": pd.Series(dtype="str"),
            "threshold": pd.Series(dtype="float64"),
            "false_positive_rate": pd.Series(dtype="float64"),
            "true_positive_rate": pd.Series(dtype="float64"),
        }
    )


def empty_pr_curve_frame() -> pd.DataFrame:
    """Return an empty Precision-Recall curve frame with stable column dtypes."""
    return pd.DataFrame(
        {
            "model_type": pd.Series(dtype="str"),
            "model_version": pd.Series(dtype="str"),
            "split": pd.Series(dtype="str"),
            "threshold": pd.Series(dtype="float64"),
            "precision": pd.Series(dtype="float64"),
            "recall": pd.Series(dtype="float64"),
        }
    )


def aligned_threshold_series(
    thresholds,
    curve_length: int,
) -> pd.Series:
    """Align sklearn thresholds to curve points and use nulls where absent."""
    threshold_values = list(thresholds)
    if len(threshold_values) < curve_length:
        threshold_values.extend([None] * (curve_length - len(threshold_values)))
    if len(threshold_values) > curve_length:
        threshold_values = threshold_values[:curve_length]

    threshold_series = pd.to_numeric(
        pd.Series(threshold_values),
        errors="coerce",
    )
    return threshold_series.mask(threshold_series.isin([float("inf"), float("-inf")]))


def build_roc_curve(
    spec: ModelSpec,
    y_test: pd.Series,
    y_probability: pd.Series,
    warnings: list[str],
) -> pd.DataFrame:
    """Build selected-model ROC curve points on the held-out test split."""
    if y_test.nunique() < 2:
        warnings.append(
            "ROC curve was not computed because the test split has one class."
        )
        return empty_roc_curve_frame()

    false_positive_rate, true_positive_rate, thresholds = roc_curve(
        y_test,
        y_probability,
    )
    return pd.DataFrame(
        {
            "model_type": spec.model_type,
            "model_version": spec.model_version,
            "split": "test",
            "threshold": aligned_threshold_series(
                thresholds,
                len(false_positive_rate),
            ),
            "false_positive_rate": false_positive_rate,
            "true_positive_rate": true_positive_rate,
        },
        columns=ROC_CURVE_COLUMNS,
    )


def build_pr_curve(
    spec: ModelSpec,
    y_test: pd.Series,
    y_probability: pd.Series,
    warnings: list[str],
) -> pd.DataFrame:
    """Build selected-model Precision-Recall curve points on the test split."""
    if y_test.nunique() < 2:
        warnings.append(
            "Precision-Recall curve was not computed because the test split has "
            "one class."
        )
        return empty_pr_curve_frame()

    precision_values, recall_values, thresholds = precision_recall_curve(
        y_test,
        y_probability,
    )
    return pd.DataFrame(
        {
            "model_type": spec.model_type,
            "model_version": spec.model_version,
            "split": "test",
            "threshold": aligned_threshold_series(
                thresholds,
                len(precision_values),
            ),
            "precision": precision_values,
            "recall": recall_values,
        },
        columns=PR_CURVE_COLUMNS,
    )


def build_model_comparison(
    results: list[dict],
    selected_result: dict,
    selection_reason: str,
) -> pd.DataFrame:
    """Build one comparison row per evaluated model candidate."""
    rows = []
    for result in results:
        metrics = result["metrics"]
        row = {
            column: metrics.get(column)
            for column in MODEL_COMPARISON_COLUMNS
            if column not in {"selected_model", "selection_reason"}
        }
        row["selected_model"] = result is selected_result
        row["selection_reason"] = selection_reason if result is selected_result else ""
        rows.append(row)
    return pd.DataFrame(rows, columns=MODEL_COMPARISON_COLUMNS)


def metrics_table_frame(metrics: dict) -> pd.DataFrame:
    """Build a one-row metrics frame with dashboard-friendly scalar values."""
    table_metrics = metrics.copy()
    table_metrics["warnings"] = "; ".join(table_metrics.get("warnings", []))
    return pd.DataFrame([table_metrics])


def write_runtime_outputs(
    predictions: pd.DataFrame,
    metrics: dict,
    feature_importance: pd.DataFrame,
    model_comparison: pd.DataFrame,
    roc_curve_data: pd.DataFrame,
    pr_curve_data: pd.DataFrame,
    predictions_output: Path,
    metrics_output: Path,
    feature_importance_output: Path,
    model_comparison_output: Path,
    roc_curve_output: Path,
    pr_curve_output: Path,
) -> None:
    """Write local runtime prediction, metrics, comparison, and curve artifacts."""
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    feature_importance_output.parent.mkdir(parents=True, exist_ok=True)
    model_comparison_output.parent.mkdir(parents=True, exist_ok=True)
    roc_curve_output.parent.mkdir(parents=True, exist_ok=True)
    pr_curve_output.parent.mkdir(parents=True, exist_ok=True)

    predictions.to_csv(predictions_output, index=False)
    metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    feature_importance.to_csv(feature_importance_output, index=False)
    model_comparison.to_csv(model_comparison_output, index=False)
    roc_curve_data.to_csv(roc_curve_output, index=False)
    pr_curve_data.to_csv(pr_curve_output, index=False)


def write_duckdb_serving_tables(
    duckdb_path: Path,
    predictions: pd.DataFrame,
    metrics: dict,
    feature_importance: pd.DataFrame,
    model_comparison: pd.DataFrame,
    roc_curve_data: pd.DataFrame,
    pr_curve_data: pd.DataFrame,
) -> None:
    """Create or replace dashboard-ready ML serving tables in DuckDB."""
    frames_to_write = [
        (
            "ml_withdrawal_predictions_frame",
            SERVING_TABLES["predictions"],
            predictions,
        ),
        (
            "ml_withdrawal_metrics_frame",
            SERVING_TABLES["metrics"],
            metrics_table_frame(metrics),
        ),
        (
            "ml_withdrawal_feature_importance_frame",
            SERVING_TABLES["feature_importance"],
            feature_importance,
        ),
        (
            "ml_withdrawal_model_comparison_frame",
            SERVING_TABLES["model_comparison"],
            model_comparison,
        ),
        (
            "ml_withdrawal_roc_curve_frame",
            SERVING_TABLES["roc_curve"],
            roc_curve_data,
        ),
        (
            "ml_withdrawal_pr_curve_frame",
            SERVING_TABLES["pr_curve"],
            pr_curve_data,
        ),
    ]

    with duckdb.connect(str(duckdb_path)) as connection:
        for frame_name, table_name, data_frame in frames_to_write:
            connection.register(frame_name, data_frame)
            connection.execute(
                f"create or replace table {table_name} as select * from {frame_name}"
            )
            connection.unregister(frame_name)


def main() -> None:
    """Train, compare, and serve leakage-safe withdrawal prediction models."""
    args = parse_args()
    project_root = get_project_root()
    duckdb_path = resolve_project_path(project_root, args.duckdb_path)
    predictions_output = resolve_project_path(project_root, args.predictions_output)
    metrics_output = resolve_project_path(project_root, args.metrics_output)
    feature_importance_output = resolve_project_path(
        project_root,
        args.feature_importance_output,
    )
    model_comparison_output = resolve_project_path(
        project_root,
        args.model_comparison_output,
    )
    roc_curve_output = resolve_project_path(project_root, args.roc_curve_output)
    pr_curve_output = resolve_project_path(project_root, args.pr_curve_output)

    data = load_feature_mart(duckdb_path)
    require_columns(data)
    data[TARGET_COLUMN] = target_to_binary(data[TARGET_COLUMN])
    data = assign_temporal_split(data)

    prediction_days = sorted(data["prediction_day"].dropna().unique())
    if len(prediction_days) != 1:
        raise ValueError("Expected exactly one prediction_day in the feature mart.")
    prediction_day = int(prediction_days[0])

    feature_columns = select_feature_columns(data)
    numeric_columns, categorical_columns = split_feature_types(data, feature_columns)
    data = prepare_categorical_features(data, categorical_columns)

    train_data = data[data["split"] == "train"].copy()
    test_data = data[data["split"] == "test"].copy()
    generated_at = utc_timestamp()
    model_results = [
        fit_and_evaluate_model(
            spec=spec,
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            feature_columns=feature_columns,
            train_data=train_data,
            test_data=test_data,
            data=data,
            prediction_day=prediction_day,
            generated_at=generated_at,
        )
        for spec in get_model_specs()
    ]

    selected_result = select_best_model(model_results)
    selection_reason = build_selection_reason(selected_result, model_results)
    selected_spec = selected_result["spec"]
    selected_metrics = selected_result["metrics"].copy()
    selected_metrics["warnings"] = list(selected_metrics.get("warnings", []))
    selected_metrics["selected_model"] = True
    selected_metrics["selection_reason"] = selection_reason

    feature_importance = extract_feature_importance(
        model=selected_result["model"],
        spec=selected_spec,
        warnings=selected_metrics["warnings"],
    )
    roc_curve_data = build_roc_curve(
        spec=selected_spec,
        y_test=selected_result["y_test"],
        y_probability=selected_result["test_probabilities"],
        warnings=selected_metrics["warnings"],
    )
    pr_curve_data = build_pr_curve(
        spec=selected_spec,
        y_test=selected_result["y_test"],
        y_probability=selected_result["test_probabilities"],
        warnings=selected_metrics["warnings"],
    )
    predictions = build_predictions(
        data_frame=data,
        probabilities=selected_result["all_probabilities"],
        model_version=selected_spec.model_version,
    )
    model_comparison = build_model_comparison(
        results=model_results,
        selected_result=selected_result,
        selection_reason=selection_reason,
    )

    write_runtime_outputs(
        predictions=predictions,
        metrics=selected_metrics,
        feature_importance=feature_importance,
        model_comparison=model_comparison,
        roc_curve_data=roc_curve_data,
        pr_curve_data=pr_curve_data,
        predictions_output=predictions_output,
        metrics_output=metrics_output,
        feature_importance_output=feature_importance_output,
        model_comparison_output=model_comparison_output,
        roc_curve_output=roc_curve_output,
        pr_curve_output=pr_curve_output,
    )
    write_duckdb_serving_tables(
        duckdb_path=duckdb_path,
        predictions=predictions,
        metrics=selected_metrics,
        feature_importance=feature_importance,
        model_comparison=model_comparison,
        roc_curve_data=roc_curve_data,
        pr_curve_data=pr_curve_data,
    )
    print(
        "Wrote withdrawal model predictions, metrics, feature importance, "
        "model comparison, held-out curves, and DuckDB serving tables for "
        f"{len(predictions):,} student-module attempts. Selected "
        f"{selected_spec.model_type}."
    )


if __name__ == "__main__":
    main()
