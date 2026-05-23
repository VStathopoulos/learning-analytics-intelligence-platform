select
    code_module,
    code_presentation,
    cast(id_student as integer) as id_student,
    cast(id_site as integer) as id_site,
    cast("date" as integer) as "date",
    cast(sum_click as integer) as sum_click
from {{ source('raw_oulad', 'raw_student_vle') }}
