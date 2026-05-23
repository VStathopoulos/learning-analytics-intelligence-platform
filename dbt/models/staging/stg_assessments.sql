select
    code_module,
    code_presentation,
    cast(id_assessment as integer) as id_assessment,
    assessment_type,
    cast("date" as integer) as "date",
    cast(weight as double) as weight
from {{ source('raw_oulad', 'raw_assessments') }}

