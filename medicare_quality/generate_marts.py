import os

FILES = {}

FILES["models/marts/dim_provider.sql"] = """{{
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
"""

FILES["models/marts/fct_quality.sql"] = """{{
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
"""

FILES["models/marts/mart_cost_vs_quality.sql"] = """{{
    config(materialized='table')
}}

/*
    The analytical question: do hospitals that charge more deliver
    better outcomes?

    Joins discharge-weighted inpatient charges to CMS quality ratings
    and readmission rates at provider level. Uses 2024 charges against
    the most recent quality vintage.

    Only 2,883 of 2,906 inpatient providers appear in Care Compare, and
    Care Compare covers roughly 5,400 facilities overall - the surplus
    being critical access, psychiatric, and children's hospitals that
    do not bill through IPPS. This is an inner join, so the mart covers
    the overlap only.
*/

with costs as (

    select *
    from {{ ref('int_provider_costs') }}
    where release_year = (select max(release_year) from {{ ref('int_provider_costs') }})

),

providers as (

    select * from {{ ref('dim_provider') }}

),

readmission as (

    select
        provider_ccn,
        avg(score) as avg_readmission_rate
    from {{ ref('fct_quality') }}
    where measure_domain = 'Unplanned Visits'
      and measure_id ilike 'READM%'
      and score is not null
      and vintage = (select max(vintage) from {{ ref('fct_quality') }})
    group by provider_ccn

),

mortality as (

    select
        provider_ccn,
        avg(score) as avg_mortality_rate
    from {{ ref('fct_quality') }}
    where measure_domain = 'Complications & Deaths'
      and measure_id ilike 'MORT%'
      and score is not null
      and vintage = (select max(vintage) from {{ ref('fct_quality') }})
    group by provider_ccn

),

spending as (

    select
        provider_ccn,
        max(score) as medicare_spending_ratio
    from {{ ref('fct_quality') }}
    where measure_domain = 'Spending'
      and score is not null
      and vintage = (select max(vintage) from {{ ref('fct_quality') }})
    group by provider_ccn

),

final as (

    select
        p.provider_ccn,
        p.provider_name,
        p.state,
        p.hospital_type,
        p.hospital_ownership,
        p.is_safety_net,
        p.overall_star_rating,
        p.quality_tier,

        c.total_discharges,
        c.drg_count,
        c.weighted_avg_charge,
        c.weighted_avg_medicare_payment,
        c.payment_to_charge_ratio,
        c.unweighted_avg_charge,

        round(c.unweighted_avg_charge - c.weighted_avg_charge, 2)
                                                 as weighting_gap,

        r.avg_readmission_rate,
        m.avg_mortality_rate,
        s.medicare_spending_ratio,

        ntile(4) over (order by c.weighted_avg_charge)
                                                 as charge_quartile,

        c.release_year

    from costs c
    inner join providers p on c.provider_ccn = p.provider_ccn
    left join readmission r on c.provider_ccn = r.provider_ccn
    left join mortality m on c.provider_ccn = m.provider_ccn
    left join spending s on c.provider_ccn = s.provider_ccn

)

select * from final
"""

FILES["models/marts/_marts_models.yml"] = """version: 2

models:
  - name: dim_provider
    description: Provider dimension at the latest vintage.
    columns:
      - name: provider_ccn
        data_tests: [unique, not_null]
      - name: quality_tier
        data_tests:
          - accepted_values:
              values: ['High', 'Average', 'Low', 'Not Rated']

  - name: fct_quality
    description: Quality measures with footnote text resolved.
    columns:
      - name: quality_measure_key
        data_tests: [unique, not_null]
      - name: provider_ccn
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_provider')
              field: provider_ccn
              config:
                severity: warn

  - name: mart_cost_vs_quality
    description: >
      Provider-level join of inpatient charges to quality outcomes.
      The analytical output of the warehouse.
    columns:
      - name: provider_ccn
        data_tests: [unique, not_null]
      - name: charge_quartile
        data_tests:
          - accepted_values:
              values: [1, 2, 3, 4]
              quote: false
"""

for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote {path}")