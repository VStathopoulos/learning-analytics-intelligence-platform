select
    cast(id_assessment as integer) as id_assessment,
    cast(id_student as integer) as id_student,
    cast(date_submitted as integer) as date_submitted,
    cast(is_banked as integer) as is_banked,
    cast(score as double) as score
from {{ source('raw_oulad', 'raw_student_assessment') }}

