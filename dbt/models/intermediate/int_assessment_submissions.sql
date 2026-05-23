with student_assessment as (
    select
        id_assessment,
        id_student,
        date_submitted,
        is_banked,
        score
    from {{ ref('stg_student_assessment') }}
),

assessments as (
    select
        code_module,
        code_presentation,
        id_assessment,
        assessment_type,
        "date" as assessment_date,
        weight
    from {{ ref('stg_assessments') }}
)

select
    assessments.code_module,
    assessments.code_presentation,
    student_assessment.id_assessment,
    student_assessment.id_student,
    assessments.assessment_type,
    assessments.assessment_date,
    student_assessment.date_submitted,
    case
        when assessments.assessment_date is not null
            then student_assessment.date_submitted - assessments.assessment_date
    end as submission_delay_days,
    student_assessment.is_banked,
    student_assessment.score,
    assessments.weight,
    case
        when student_assessment.score is not null and assessments.weight is not null
            then student_assessment.score * assessments.weight / 100.0
    end as weighted_score
from student_assessment
left join assessments
    on student_assessment.id_assessment = assessments.id_assessment

