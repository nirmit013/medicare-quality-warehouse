{{
    config(materialized='table')
}}

/*
    Quality measure fact table.
    Grain: one row per provider per measure per vintage.
*/

select
    q.quality_measure_key,
    q.provider_ccn,
    q.measure_id,
    q.measure_name,
    q.measure_domain,
    q.score,
    q.denominator,
    q.lower_estimate,
    q.higher_estimate,
    q.compared_to_national,
    q.is_suppressed,
    q.footnote_code,
    f.footnote_text,
    q.measurement_start,
    q.measurement_end,
    q.vintage_date,
    q.vintage

from {{ ref('int_quality_measures') }} q
left join {{ ref('stg_footnotes') }} f
    on q.footnote_code = f.footnote_code
   and q.vintage = f.vintage
