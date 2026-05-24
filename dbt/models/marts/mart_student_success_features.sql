with student_module as (
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
        is_withdrawn,
        has_unregistered
    from {{ ref('dim_student_module') }}
),

engagement_summary as (
    select
        code_module,
        code_presentation,
        id_student,
        first_activity_date,
        last_activity_date,
        active_days,
        total_clicks,
        average_clicks_per_active_day,
        total_active_sites,
        average_active_sites_per_active_day,
        total_activity_types,
        average_activity_types_per_active_day,
        early_total_clicks,
        late_total_clicks,
        engagement_change_ratio,
        has_declining_engagement
    from {{ ref('fct_student_engagement_summary') }}
),

assessment_summary as (
    select
        code_module,
        code_presentation,
        id_student,
        submitted_assessments,
        distinct_assessments_submitted,
        average_score,
        average_weighted_score,
        total_weighted_score,
        average_submission_delay_days,
        late_submission_count,
        banked_submission_count
    from {{ ref('fct_student_assessment_summary') }}
),

joined as (
    select
        student_module.code_module,
        student_module.code_presentation,
        student_module.id_student,
        student_module.gender,
        student_module.region,
        student_module.highest_education,
        student_module.imd_band,
        student_module.age_band,
        student_module.num_of_prev_attempts,
        student_module.studied_credits,
        student_module.disability,
        student_module.final_result,
        student_module.is_withdrawn,
        student_module.has_unregistered,
        engagement_summary.first_activity_date,
        engagement_summary.last_activity_date,
        coalesce(engagement_summary.active_days, 0) as active_days,
        coalesce(engagement_summary.total_clicks, 0) as total_clicks,
        engagement_summary.average_clicks_per_active_day,
        coalesce(engagement_summary.total_active_sites, 0) as total_active_sites,
        engagement_summary.average_active_sites_per_active_day,
        coalesce(engagement_summary.total_activity_types, 0) as total_activity_types,
        engagement_summary.average_activity_types_per_active_day,
        coalesce(engagement_summary.early_total_clicks, 0) as early_total_clicks,
        coalesce(engagement_summary.late_total_clicks, 0) as late_total_clicks,
        engagement_summary.engagement_change_ratio,
        coalesce(engagement_summary.has_declining_engagement, false) as has_declining_engagement,
        coalesce(assessment_summary.submitted_assessments, 0) as submitted_assessments,
        coalesce(assessment_summary.distinct_assessments_submitted, 0) as distinct_assessments_submitted,
        assessment_summary.average_score,
        assessment_summary.average_weighted_score,
        coalesce(assessment_summary.total_weighted_score, 0) as total_weighted_score,
        assessment_summary.average_submission_delay_days,
        coalesce(assessment_summary.late_submission_count, 0) as late_submission_count,
        coalesce(assessment_summary.banked_submission_count, 0) as banked_submission_count
    from student_module
    left join engagement_summary
        on student_module.code_module = engagement_summary.code_module
        and student_module.code_presentation = engagement_summary.code_presentation
        and student_module.id_student = engagement_summary.id_student
    left join assessment_summary
        on student_module.code_module = assessment_summary.code_module
        and student_module.code_presentation = assessment_summary.code_presentation
        and student_module.id_student = assessment_summary.id_student
),

risk_flags as (
    select
        *,
        total_clicks < 100 as is_low_engagement,
        average_score is null or average_score < 50 as is_low_assessment_score,
        coalesce(average_submission_delay_days, 0) > 0 as has_late_submission_pattern
    from joined
),

risk_scored as (
    select
        *,
        case when is_low_engagement then 1 else 0 end
        + case when has_declining_engagement then 1 else 0 end
        + case when is_low_assessment_score then 1 else 0 end
        + case when has_late_submission_pattern then 1 else 0 end
            as risk_score_simple
    from risk_flags
)

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
    is_withdrawn,
    has_unregistered,
    first_activity_date,
    last_activity_date,
    active_days,
    total_clicks,
    average_clicks_per_active_day,
    total_active_sites,
    average_active_sites_per_active_day,
    total_activity_types,
    average_activity_types_per_active_day,
    early_total_clicks,
    late_total_clicks,
    engagement_change_ratio,
    has_declining_engagement,
    submitted_assessments,
    distinct_assessments_submitted,
    average_score,
    average_weighted_score,
    total_weighted_score,
    average_submission_delay_days,
    late_submission_count,
    banked_submission_count,
    is_low_engagement,
    is_low_assessment_score,
    has_late_submission_pattern,
    risk_score_simple,
    case
        when risk_score_simple in (0, 1) then 'Low'
        when risk_score_simple = 2 then 'Medium'
        when risk_score_simple in (3, 4) then 'High'
    end as risk_band
from risk_scored
