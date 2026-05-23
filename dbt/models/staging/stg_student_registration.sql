select
    code_module,
    code_presentation,
    cast(id_student as integer) as id_student,
    cast(date_registration as integer) as date_registration,
    cast(date_unregistration as integer) as date_unregistration
from {{ source('raw_oulad', 'raw_student_registration') }}

