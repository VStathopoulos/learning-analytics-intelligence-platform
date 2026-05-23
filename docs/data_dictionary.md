# Data Dictionary

Early source-data dictionary for the Open University Learning Analytics Dataset
(OULAD).

## 1. Purpose

This document records the expected raw CSV files and core fields used by the
initial local analytics pipeline. It is focused on source-level structure, not
final dbt model definitions.

## 2. Expected Raw Files

### courses.csv

- `code_module`
- `code_presentation`
- `module_presentation_length`

### assessments.csv

- `code_module`
- `code_presentation`
- `id_assessment`
- `assessment_type`
- `date`
- `weight`

### vle.csv

- `id_site`
- `code_module`
- `code_presentation`
- `activity_type`
- `week_from`
- `week_to`

### studentInfo.csv

- `code_module`
- `code_presentation`
- `id_student`
- `gender`
- `region`
- `highest_education`
- `imd_band`
- `age_band`
- `num_of_prev_attempts`
- `studied_credits`
- `disability`
- `final_result`

### studentRegistration.csv

- `code_module`
- `code_presentation`
- `id_student`
- `date_registration`
- `date_unregistration`

### studentAssessment.csv

- `id_assessment`
- `id_student`
- `date_submitted`
- `is_banked`
- `score`

### studentVle.csv

- `code_module`
- `code_presentation`
- `id_student`
- `id_site`
- `date`
- `sum_click`

## 3. Key Identifiers And Join Fields

- `code_module`
- `code_presentation`
- `id_student`
- `id_assessment`
- `id_site`

## 4. Notes For Ingestion

- Raw CSVs should be placed under `data/raw/`.
- Source files should be loaded without destructive modification.
- Missing values should be profiled before transformation.
- Derived analytics should be built in dbt models, not manually in raw files.

## 5. Initial Analytical Themes

- Course and presentation structure.
- Student demographics and enrollment patterns.
- Assessment timing, submission behavior, and performance.
- VLE activity and engagement over time.
- Relationships between participation, assessment outcomes, and final results.
