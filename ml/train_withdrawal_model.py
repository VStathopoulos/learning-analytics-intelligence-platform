"""Train a leakage-safe day-30 withdrawal prediction baseline model."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SOURCE_TABLE = "mart_withdrawal_prediction_features"
MODEL_VERSION = "logistic_regression_day30_v1"
TARGET_COLUMN = "withdraw_after_day_30"
MISSING_CATEGORY = "__missing__"
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
    "coefficient",
    "abs_coefficient",
    "model_version",
]


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
            "Train a leakage-safe Logistic Regression baseline for day-30 "
            "withdrawal prediction."
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
        help="Path for scored withdrawal predictions.",
    )
    parser.add_argument(
        "--metrics-output",
        default="data/processed/ml_withdrawal_metrics.json",
        help="Path for model evaluation metrics.",
    )
    parser.add_argument(
        "--feature-importance-output",
        default="data/processed/ml_withdrawal_feature_importance.csv",
        help="Path for Logistic Regression feature coefficients.",
    )
    return parser.parse_args()


def load_feature_mart(duckdb_path: Path) -> pd.DataFrame:
    """Load the approved leakage-safe withdrawal prediction mart."""
    if not duckdb_path.exists():
        raise FileNotFoundError(
            f"DuckDB warehouse not found at {duckdb_path}. Run ingestion and dbt "
            "before training the withdrawal baseline."
        )

    try:
        with duckdb.connect(str(duckdb_path), read_only=True) as connection:
            return connection.execute(
                "select * from mart_withdrawal_prediction_features"
            ).fetchdf()
    except duckdb.Error as exc:
        raise RuntimeError(
            "Could not load mart_withdrawal_prediction_features from DuckDB. "
            "Run dbt before training the withdrawal baseline."
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


def build_model_pipeline(
    numeric_columns: list[str],
    categorical_columns: list[str],
) -> Pipeline:
    """Build the preprocessing and Logistic Regression pipeline."""
    transformers = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
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
            (
                "model",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
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


def build_metrics(
    y_train: pd.Series,
    y_test: pd.Series,
    y_pred: pd.Series,
    y_probability: pd.Series,
    prediction_day: int,
    warnings: list[str],
) -> dict:
    """Build model evaluation metrics for the held-out presentation."""
    roc_auc, roc_auc_warning = safe_roc_auc(y_test, y_probability)
    if roc_auc_warning:
        warnings.append(roc_auc_warning)

    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        y_test,
        y_pred,
        labels=[0, 1],
    ).ravel()

    return {
        "model_type": "LogisticRegression",
        "model_version": MODEL_VERSION,
        "target": TARGET_COLUMN,
        "prediction_day": prediction_day,
        "split_strategy": "Train on presentations before the latest; test on latest presentation.",
        "generated_at": utc_timestamp(),
        "train_rows": int(len(y_train)),
        "test_rows": int(len(y_test)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "roc_auc": roc_auc,
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


def build_predictions(
    data_frame: pd.DataFrame,
    probabilities: pd.Series,
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
    predictions["model_version"] = MODEL_VERSION
    return predictions[PREDICTION_COLUMNS]


def extract_feature_importance(model: Pipeline, warnings: list[str]) -> pd.DataFrame:
    """Extract Logistic Regression coefficients for transformed features."""
    try:
        feature_names = model.named_steps["preprocessor"].get_feature_names_out()
        coefficients = model.named_steps["model"].coef_[0]
    except (AttributeError, KeyError, IndexError, ValueError) as exc:
        warnings.append(f"Feature importance could not be extracted: {exc}")
        return pd.DataFrame(columns=FEATURE_IMPORTANCE_COLUMNS)

    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "coefficient": coefficients,
        }
    )
    importance["abs_coefficient"] = importance["coefficient"].abs()
    importance["model_version"] = MODEL_VERSION
    return importance.sort_values("abs_coefficient", ascending=False)[
        FEATURE_IMPORTANCE_COLUMNS
    ]


def write_outputs(
    predictions: pd.DataFrame,
    metrics: dict,
    feature_importance: pd.DataFrame,
    predictions_output: Path,
    metrics_output: Path,
    feature_importance_output: Path,
) -> None:
    """Write local runtime prediction, metrics, and feature importance artifacts."""
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    feature_importance_output.parent.mkdir(parents=True, exist_ok=True)

    predictions.to_csv(predictions_output, index=False)
    metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    feature_importance.to_csv(feature_importance_output, index=False)


def main() -> None:
    """Train and score the leakage-safe withdrawal baseline."""
    args = parse_args()
    project_root = get_project_root()
    duckdb_path = resolve_project_path(project_root, args.duckdb_path)
    predictions_output = resolve_project_path(project_root, args.predictions_output)
    metrics_output = resolve_project_path(project_root, args.metrics_output)
    feature_importance_output = resolve_project_path(
        project_root,
        args.feature_importance_output,
    )

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
    model = build_model_pipeline(numeric_columns, categorical_columns)

    train_data = data[data["split"] == "train"].copy()
    test_data = data[data["split"] == "test"].copy()
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
    feature_importance = extract_feature_importance(model, warnings)
    metrics = build_metrics(
        y_train=y_train,
        y_test=y_test,
        y_pred=test_predictions,
        y_probability=test_probabilities,
        prediction_day=prediction_day,
        warnings=warnings,
    )
    predictions = build_predictions(data, all_probabilities)

    write_outputs(
        predictions=predictions,
        metrics=metrics,
        feature_importance=feature_importance,
        predictions_output=predictions_output,
        metrics_output=metrics_output,
        feature_importance_output=feature_importance_output,
    )
    print(
        "Wrote withdrawal model predictions, metrics, and feature importance "
        f"for {len(predictions):,} student-module attempts."
    )


if __name__ == "__main__":
    main()
