# Withdrawal Prediction Baseline

This directory contains a leakage-safe baseline training script for day-30
withdrawal prediction.

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

## Model

The first baseline model is Logistic Regression with preprocessing handled by a
scikit-learn pipeline:

- Numeric features: median imputation and standard scaling.
- Categorical features: most-frequent imputation and one-hot encoding.
- Class balancing enabled with `class_weight="balanced"`.

Evaluation uses a temporal split: the latest available course presentation is
held out for testing, and earlier presentations are used for training.

## Runtime Outputs

The training script writes dashboard-ready runtime artifacts:

- `data/processed/ml_withdrawal_predictions.csv`
- `data/processed/ml_withdrawal_metrics.json`
- `data/processed/ml_withdrawal_feature_importance.csv`

These outputs are generated artifacts and should not be committed.

## Usage

Run from the project root after the DuckDB warehouse and dbt mart exist:

```bash
python ml/train_withdrawal_model.py
```

The future dashboard ML section should consume these generated outputs. Dash
should not train the model.
