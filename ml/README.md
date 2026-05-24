# Withdrawal Prediction Models

This directory contains a leakage-safe training script for day-30 withdrawal
prediction.

## Task

The ML task is to predict whether a student-module attempt will withdraw after
course day 30.

Prediction population:

- Students still enrolled after day 30.
- Students withdrawn on or before day 30 are excluded by the dbt feature mart.

Feature timing:

- Features are limited to information available on or before day 30.
- The model reads only the approved dbt mart
  `mart_withdrawal_prediction_features`.

## Models

The script trains two candidate models on the same leakage-safe temporal split:

- Logistic Regression baseline with `class_weight="balanced"`.
- Random Forest challenger with class balancing and a fixed random seed.

Preprocessing is handled with scikit-learn pipelines:

- Logistic Regression numeric features: median imputation and standard scaling.
- Random Forest numeric features: median imputation.
- Categorical features: missing-value handling and one-hot encoding.

The selected model is chosen by held-out ROC AUC. If held-out ROC AUC ties,
Logistic Regression is preferred for interpretability. If held-out ROC AUC is
null for a model, that model is ranked last.

The script also writes held-out ROC and Precision-Recall curve outputs for the
selected model. These curves are computed on the held-out test split only.

## Runtime Outputs

The training script writes dashboard-ready runtime files:

- `data/processed/ml_withdrawal_predictions.csv`
- `data/processed/ml_withdrawal_metrics.json`
- `data/processed/ml_withdrawal_feature_importance.csv`
- `data/processed/ml_withdrawal_model_comparison.csv`
- `data/processed/ml_withdrawal_roc_curve.csv`
- `data/processed/ml_withdrawal_pr_curve.csv`

These outputs are generated artifacts and should not be committed.

## DuckDB Serving Tables

The training script also creates or replaces dashboard-ready ML serving tables
in the local DuckDB warehouse:

- `ml_withdrawal_predictions`
- `ml_withdrawal_metrics`
- `ml_withdrawal_feature_importance`
- `ml_withdrawal_model_comparison`
- `ml_withdrawal_roc_curve`
- `ml_withdrawal_pr_curve`

The future dashboard should consume the DuckDB ML serving tables. Dash should
not train models or compute ROC and Precision-Recall curves using scikit-learn
inside Dash.

## Usage

Run from the project root after the DuckDB warehouse and dbt mart exist:

```bash
python ml/train_withdrawal_model.py
```
