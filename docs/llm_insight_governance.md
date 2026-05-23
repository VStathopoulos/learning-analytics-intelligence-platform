# LLM Insight Governance

Early governance note for the future LLM-assisted insight layer.

## 1. Purpose

The LLM insight layer will support grounded narrative summaries for OULAD
learning analytics. It is deferred until ingestion, dbt marts, and dashboard
basics are working.

The goal is to generate insight cards based on approved analytical outputs, not
unsupported recommendations or direct student-level analysis.

## 2. Core Rule

The LLM must not read raw student-level records.

## 3. Allowed Inputs

- Approved aggregate dbt marts.
- Precomputed dashboard summary tables.
- Documented metric definitions and population scopes.

## 4. Disallowed Inputs

- Raw OULAD CSV files.
- Raw or lightly staged student-level records.
- Free-form database access to unrestricted tables.
- Personally identifying or row-level student narratives.

## 5. Required Insight Card Fields

- `title`
- `metric_name`
- `population_scope`
- `time_or_course_scope`
- `observation`
- `supporting_values`
- `interpretation`
- `limitations`
- `generated_at`

## 6. Human Review

LLM-generated insight cards should be reviewed before being treated as final
analysis. Review should confirm that observations are grounded in the supplied
aggregate values, limitations are explicit, and the wording does not imply
causality or recommendations beyond the evidence.

## 7. Deferred Implementation

Implementation is intentionally deferred until the manual data pipeline,
dbt marts, and initial Dash dashboard are working. Future work should define
approved mart inputs, output schemas, prompt templates, and evaluation checks
before enabling LLM-generated insights.
