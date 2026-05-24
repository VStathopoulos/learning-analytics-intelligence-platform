with assessment_submissions as (
    select
        code_module,
        code_presentation,
        id_assessment,
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
    id_student,
    count(*) as submitted_assessments,
    count(distinct id_assessment) as distinct_assessments_submitted,
    avg(score) as average_score,
    avg(weighted_score) as average_weighted_score,
    sum(weighted_score) as total_weighted_score,
    avg(submission_delay_days) as average_submission_delay_days,
    sum(
        case
            when submission_delay_days > 0 then 1
            else 0
        end
    ) as late_submission_count,
    sum(is_banked) as banked_submission_count
from assessment_submissions
group by
    code_module,
    code_presentation,
    id_student
