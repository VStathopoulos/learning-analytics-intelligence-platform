select
    code_module,
    code_presentation,
    cast(id_student as integer) as id_student,
    gender,
    region,
    highest_education,
    imd_band,
    age_band,
    cast(num_of_prev_attempts as integer) as num_of_prev_attempts,
    cast(studied_credits as integer) as studied_credits,
    disability,
    final_result
from {{ source('raw_oulad', 'raw_student_info') }}

