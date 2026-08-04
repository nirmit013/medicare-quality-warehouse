{{
    config(materialized='view')
}}

/*
    Standardized infection ratios. Values above 1.0 indicate more infections than predicted.

    Grain: one row per provider per measure per vintage.

    SCORE arrives as text because CMS writes 'Not Available' and
    'Not Applicable' into the same column as real values. TRY_CAST
    converts what it can and returns NULL for the rest, so suppression
    stays visible as NULL rather than silently failing the load.

    Columns not present in this source are cast as NULL so every
    staging model shares one shape and can be unioned downstream.
*/

with source as (

    select * from {{ source('cms_raw', 'infections') }}

),

renamed as (

    select
        {{ clean_ccn('facility_id') }}          as provider_ccn,
        trim(measure_id)                         as measure_id,
        trim(measure_name)                       as measure_name,
        'Healthcare-Associated Infections'                               as measure_domain,

        try_cast(score as float)                 as score,
        cast(null as int)                        as denominator,
        cast(null as float)                      as lower_estimate,
        cast(null as float)                      as higher_estimate,
        trim(compared_to_national)               as compared_to_national,
        cast(null as int)                        as patients_returned,

        trim(footnote)                           as footnote_code,
        try_cast(start_date as date)             as measurement_start,
        try_cast(end_date as date)               as measurement_end,

        to_date(vintage, 'YYYY-MM-DD')           as vintage_date,
        vintage                                  as vintage

    from source
    where facility_id is not null
      and measure_id is not null

)

select * from renamed
