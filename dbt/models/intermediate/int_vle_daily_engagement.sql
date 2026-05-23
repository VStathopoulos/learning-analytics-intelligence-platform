with student_vle as (
    select
        code_module,
        code_presentation,
        id_student,
        id_site,
        "date",
        sum_click
    from {{ ref('stg_student_vle') }}
),

vle as (
    select
        id_site,
        activity_type
    from {{ ref('stg_vle') }}
)

select
    student_vle.code_module,
    student_vle.code_presentation,
    student_vle.id_student,
    student_vle."date" as activity_date,
    sum(student_vle.sum_click) as total_clicks,
    count(distinct student_vle.id_site) as active_site_count,
    count(distinct vle.activity_type) as activity_type_count
from student_vle
left join vle
    on student_vle.id_site = vle.id_site
group by
    student_vle.code_module,
    student_vle.code_presentation,
    student_vle.id_student,
    student_vle."date"
