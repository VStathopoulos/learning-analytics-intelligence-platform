select
    cast(id_site as integer) as id_site,
    code_module,
    code_presentation,
    activity_type,
    cast(week_from as integer) as week_from,
    cast(week_to as integer) as week_to
from {{ source('raw_oulad', 'raw_vle') }}

