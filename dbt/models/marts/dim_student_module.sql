select distinct
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
    date_unregistration,
    is_withdrawn,
    has_unregistered
from {{ ref('int_student_module_enrollments') }}

