{{
    config(materialized='table')
}}

/*
    Provider dimension, current state.

    Uses the latest vintage as the current record. A future iteration
    could snapshot this as SCD Type 2 - 559 providers entered or exited
    across the four snapshots, so history is meaningful here.

    The is_safety_net flag exists because payment-to-charge ratios above
    1.0 concentrate in public and tribal facilities. Pooling them with
    private systems in a cost comparison would confound the result.
*/

with latest as (

    select * from {{ ref('stg_provider') }}
    where vintage = (select max(vintage) from {{ ref('stg_provider') }})

),

first_seen as (

    select provider_ccn, min(vintage_date) as first_seen_date
    from {{ ref('stg_provider') }}
    group by provider_ccn

),

final as (

    select
        l.provider_ccn,
        l.provider_name,
        l.city,
        l.state,
        l.zip_code,
        l.county,
        l.hospital_type,
        l.hospital_ownership,
        l.emergency_services,
        l.overall_star_rating,

        case
            when l.hospital_ownership ilike 'Government%' then true
            when l.hospital_ownership ilike '%Tribal%' then true
            else false
        end                                      as is_safety_net,

        case
            when l.overall_star_rating >= 4 then 'High'
            when l.overall_star_rating = 3 then 'Average'
            when l.overall_star_rating <= 2 then 'Low'
            else 'Not Rated'
        end                                      as quality_tier,

        f.first_seen_date,
        l.vintage_date                           as current_as_of

    from latest l
    left join first_seen f on l.provider_ccn = f.provider_ccn

)

select * from final
