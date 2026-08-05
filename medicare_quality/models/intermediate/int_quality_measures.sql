{{
    config(materialized='view')
}}

/*
    All non-HCAHPS quality measures in one table.

    The four source files share a common core - provider, measure, score,
    footnote, dates - and differ only in which extras they carry. Staging
    casts the missing ones as NULL so they union cleanly here.

    HCAHPS is deliberately excluded: it has four independent footnote
    columns and a different value structure, so forcing it into this
    shape would lose information.

    Grain: one row per provider per measure per vintage.
*/

with complications as (
    select * from {{ ref('stg_complications_deaths') }}
),

unplanned as (
    select * from {{ ref('stg_unplanned_visits') }}
),

infections as (
    select * from {{ ref('stg_infections') }}
),

spending as (
    select * from {{ ref('stg_spending_per_patient') }}
),

unioned as (
    select * from complications
    union all
    select * from unplanned
    union all
    select * from infections
    union all
    select * from spending
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'provider_ccn', 'measure_id', 'vintage'
        ]) }}                                    as quality_measure_key,
        provider_ccn,
        measure_id,
        measure_name,
        measure_domain,
        score,
        denominator,
        lower_estimate,
        higher_estimate,
        compared_to_national,
        patients_returned,
        footnote_code,
        case when score is null and footnote_code is not null
             then true else false end            as is_suppressed,
        measurement_start,
        measurement_end,
        vintage_date,
        vintage
    from unioned
)

select * from final
