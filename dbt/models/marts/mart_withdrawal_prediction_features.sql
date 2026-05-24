with prediction_config as (
    select 30 as prediction_day
),

student_module as (
    select
        code_module,
        code_presentation,
        id_student,
        gender,
        region,
        highest_education,
        imd_band,
        age_band,
        num_of_prev_attempts,
        studied_credits,
        disability,
        final_result,
        date_registration,
        date_unregistration
    from {{ ref('dim_student_module') }}
),

eligible_students as (
    select
        student_module.code_module,
        student_module.code_presentation,
        student_module.id_student,
        prediction_config.prediction_day,
        student_module.gender,
        student_module.region,
        student_module.highest_education,
        student_module.imd_band,
        student_module.age_band,
        student_module.num_of_prev_attempts,
        student_module.studied_credits,
        student_module.disability,
        student_module.final_result,
        student_module.date_registration,
        student_module.date_unregistration,
        student_module.date_registration < 0 as registered_before_course_start,
        prediction_config.prediction_day
        - student_module.date_registration as registration_to_prediction_days
    from student_module
    cross join prediction_config
    where
        student_module.date_unregistration is null
        or student_module.date_unregistration > prediction_config.prediction_day
),

student_vle as (
    select
        code_module,
        code_presentation,
        id_student,
        id_site,
        "date" as activity_date,
        sum_click
    from {{ ref('stg_student_vle') }}
    where "date" <= 30
),

vle as (
    select
        code_module,
        code_presentation,
        id_site,
        activity_type
    from {{ ref('stg_vle') }}
),

early_vle_engagement as (
    select
        student_vle.code_module,
        student_vle.code_presentation,
        student_vle.id_student,
        sum(student_vle.sum_click) as early_total_clicks,
        count(distinct student_vle.activity_date) as early_active_days,
        count(distinct student_vle.id_site) as early_distinct_sites,
        count(distinct vle.activity_type) as early_distinct_activity_types
    from student_vle
    left join vle
        on student_vle.code_module = vle.code_module
        and student_vle.code_presentation = vle.code_presentation
        and student_vle.id_site = vle.id_site
    group by
        student_vle.code_module,
        student_vle.code_presentation,
        student_vle.id_student
),

early_assessment_submissions as (
    select
        code_module,
        code_presentation,
        id_student,
        count(*) as early_submitted_assessments,
        avg(score) as early_average_score,
        sum(weighted_score) as early_weighted_score,
        sum(
            case
                when submission_delay_days > 0 then 1
                else 0
            end
        ) as early_late_submissions
    from {{ ref('int_assessment_submissions') }}
    where date_submitted <= 30
    group by
        code_module,
        code_presentation,
        id_student
)

select
    eligible_students.code_module,
    eligible_students.code_presentation,
    eligible_students.id_student,
    eligible_students.prediction_day,
    case
        when
            eligible_students.final_result = 'Withdrawn'
            and eligible_students.date_unregistration > eligible_students.prediction_day
            then true
        else false
    end as withdraw_after_day_30,
    eligible_students.gender,
    eligible_students.region,
    eligible_students.highest_education,
    eligible_students.imd_band,
    eligible_students.age_band,
    eligible_students.num_of_prev_attempts,
    eligible_students.studied_credits,
    eligible_students.disability,
    eligible_students.date_registration,
    eligible_students.registered_before_course_start,
    eligible_students.registration_to_prediction_days,
    coalesce(early_vle_engagement.early_total_clicks, 0) as early_total_clicks,
    coalesce(early_vle_engagement.early_active_days, 0) as early_active_days,
    coalesce(early_vle_engagement.early_distinct_sites, 0) as early_distinct_sites,
    coalesce(
        early_vle_engagement.early_distinct_activity_types,
        0
    ) as early_distinct_activity_types,
    case
        when coalesce(early_vle_engagement.early_active_days, 0) > 0
            then cast(early_vle_engagement.early_total_clicks as double)
                / early_vle_engagement.early_active_days
        else 0.0
    end as early_clicks_per_active_day,
    coalesce(early_vle_engagement.early_active_days, 0) > 0 as had_early_vle_activity,
    coalesce(
        early_assessment_submissions.early_submitted_assessments,
        0
    ) as early_submitted_assessments,
    early_assessment_submissions.early_average_score,
    coalesce(
        early_assessment_submissions.early_weighted_score,
        0
    ) as early_weighted_score,
    coalesce(
        early_assessment_submissions.early_late_submissions,
        0
    ) as early_late_submissions,
    coalesce(
        early_assessment_submissions.early_submitted_assessments,
        0
    ) > 0 as had_early_assessment
from eligible_students
left join early_vle_engagement
    on eligible_students.code_module = early_vle_engagement.code_module
    and eligible_students.code_presentation = early_vle_engagement.code_presentation
    and eligible_students.id_student = early_vle_engagement.id_student
left join early_assessment_submissions
    on eligible_students.code_module = early_assessment_submissions.code_module
    and eligible_students.code_presentation = early_assessment_submissions.code_presentation
    and eligible_students.id_student = early_assessment_submissions.id_student
