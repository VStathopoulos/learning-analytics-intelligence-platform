with student_info as (
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
        final_result
    from {{ ref('stg_student_info') }}
),

student_registration as (
    select
        code_module,
        code_presentation,
        id_student,
        date_registration,
        date_unregistration
    from {{ ref('stg_student_registration') }}
)

select
    student_info.code_module,
    student_info.code_presentation,
    student_info.id_student,
    student_info.gender,
    student_info.region,
    student_info.highest_education,
    student_info.imd_band,
    student_info.age_band,
    student_info.num_of_prev_attempts,
    student_info.studied_credits,
    student_info.disability,
    student_info.final_result,
    student_registration.date_registration,
    student_registration.date_unregistration,
    student_info.final_result = 'Withdrawn' as is_withdrawn,
    student_registration.date_unregistration is not null as has_unregistered
from student_info
left join student_registration
    on student_info.code_module = student_registration.code_module
    and student_info.code_presentation = student_registration.code_presentation
    and student_info.id_student = student_registration.id_student

