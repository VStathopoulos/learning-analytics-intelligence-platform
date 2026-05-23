with assessment_submissions as (
    select
        code_module,
        code_presentation,
        id_assessment,
        assessment_type,
        assessment_date,
        id_student,
        score,
        weighted_score,
        submission_delay_days,
        is_banked
    from {{ ref('int_assessment_submissions') }}
)

select
    code_module,
    code_presentation,
    id_assessment,
    assessment_type,
    assessment_date,
    count(*) as submitted_assessments,
    count(distinct id_student) as distinct_students_submitted,
    avg(score) as average_score,
    avg(weighted_score) as average_weighted_score,
    avg(submission_delay_days) as average_submission_delay_days,
    sum(is_banked) as banked_submission_count
from assessment_submissions
group by
    code_module,
    code_presentation,
    id_assessment,
    assessment_type,
    assessment_date
