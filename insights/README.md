# Governed Insight Cards

This directory contains a governed prototype for future LLM-assisted insight
generation in the Learning Analytics Intelligence Platform.

The current generator produces deterministic aggregate insight cards, not
free-form LLM prose. It does not call an external LLM API, does not require an
API key, and does not send data outside the local environment.

## Governance Boundary

- The generator reads only approved dbt mart tables from the local DuckDB
  warehouse.
- It must not read raw, staging, or intermediate dbt tables.
- It must not read raw OULAD CSV files.
- It must not include row-level student records or `id_student` in the output.
- Risk bands are rule-based analytical indicators, not validated predictive ML
  outputs.
- Future LLM components should consume only these aggregate cards or approved
  dashboard summaries.

Approved mart tables:

- `mart_student_success_features`
- `fct_course_engagement_daily`
- `fct_assessment_performance`

## Manual Usage

Run from the project root:

```bash
python insights/generate_insight_cards.py
```

Default output path:

```text
data/processed/insight_cards.json
```

Generated outputs are runtime artifacts and should not be committed.
