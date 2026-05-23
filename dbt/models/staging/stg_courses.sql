select
    code_module,
    code_presentation,
    cast(module_presentation_length as integer) as module_presentation_length
from {{ source('raw_oulad', 'raw_courses') }}

