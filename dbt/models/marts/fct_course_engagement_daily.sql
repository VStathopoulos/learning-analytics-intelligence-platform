with daily_engagement as (
    select
        code_module,
        code_presentation,
        activity_date,
        id_student,
        total_clicks,
        active_site_count,
        activity_type_count
    from {{ ref('int_vle_daily_engagement') }}
),

aggregated as (
    select
        code_module,
        code_presentation,
        activity_date,
        count(distinct id_student) as active_students,
        sum(total_clicks) as total_clicks,
        sum(active_site_count) as total_active_sites,
        sum(activity_type_count) as total_activity_types
    from daily_engagement
    group by
        code_module,
        code_presentation,
        activity_date
)

select
    code_module,
    code_presentation,
    activity_date,
    active_students,
    total_clicks,
    cast(total_clicks as double)
    / nullif(active_students, 0) as average_clicks_per_active_student,
    total_active_sites,
    cast(total_active_sites as double)
    / nullif(active_students, 0) as average_active_sites_per_active_student,
    total_activity_types,
    cast(total_activity_types as double)
    / nullif(active_students, 0) as average_activity_types_per_active_student
from aggregated

