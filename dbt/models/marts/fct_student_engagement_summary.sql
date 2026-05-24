with daily_engagement as (
    select
        code_module,
        code_presentation,
        id_student,
        activity_date,
        total_clicks,
        active_site_count,
        activity_type_count
    from {{ ref('int_vle_daily_engagement') }}
),

student_activity_window as (
    select
        code_module,
        code_presentation,
        id_student,
        min(activity_date) as first_activity_date,
        max(activity_date) as last_activity_date,
        floor((min(activity_date) + max(activity_date)) / 2.0) as activity_midpoint
    from daily_engagement
    group by
        code_module,
        code_presentation,
        id_student
),

aggregated as (
    select
        daily_engagement.code_module,
        daily_engagement.code_presentation,
        daily_engagement.id_student,
        student_activity_window.first_activity_date,
        student_activity_window.last_activity_date,
        count(distinct daily_engagement.activity_date) as active_days,
        sum(daily_engagement.total_clicks) as total_clicks,
        sum(daily_engagement.active_site_count) as total_active_sites,
        sum(daily_engagement.activity_type_count) as total_activity_types,
        sum(
            case
                when daily_engagement.activity_date <= student_activity_window.activity_midpoint
                    then daily_engagement.total_clicks
                else 0
            end
        ) as early_total_clicks,
        sum(
            case
                when daily_engagement.activity_date > student_activity_window.activity_midpoint
                    then daily_engagement.total_clicks
                else 0
            end
        ) as late_total_clicks
    from daily_engagement
    inner join student_activity_window
        on daily_engagement.code_module = student_activity_window.code_module
        and daily_engagement.code_presentation = student_activity_window.code_presentation
        and daily_engagement.id_student = student_activity_window.id_student
    group by
        daily_engagement.code_module,
        daily_engagement.code_presentation,
        daily_engagement.id_student,
        student_activity_window.first_activity_date,
        student_activity_window.last_activity_date
)

select
    code_module,
    code_presentation,
    id_student,
    first_activity_date,
    last_activity_date,
    active_days,
    total_clicks,
    cast(total_clicks as double)
    / nullif(active_days, 0) as average_clicks_per_active_day,
    total_active_sites,
    cast(total_active_sites as double)
    / nullif(active_days, 0) as average_active_sites_per_active_day,
    total_activity_types,
    cast(total_activity_types as double)
    / nullif(active_days, 0) as average_activity_types_per_active_day,
    early_total_clicks,
    late_total_clicks,
    cast(late_total_clicks as double)
    / nullif(early_total_clicks, 0) as engagement_change_ratio,
    case
        when early_total_clicks > 0 and late_total_clicks < early_total_clicks
            then true
        else false
    end as has_declining_engagement
from aggregated
