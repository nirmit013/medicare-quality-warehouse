import os

FILES = {}

FILES["models/intermediate/int_quality_measures.sql"] = """{{
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
"""

FILES["models/intermediate/int_provider_costs.sql"] = """{{
    config(materialized='view')
}}

/*
    Inpatient charges rolled up from provider-DRG grain to provider-year.

    CMS pre-aggregates the Avg_* columns across each hospital's
    discharges, so a plain average across DRG rows is an average of
    averages. Every figure here is discharge-weighted: multiply each
    average by its discharge count, sum, then divide by total discharges.

    Grain: one row per provider per release year.
*/

with charges as (

    select * from {{ ref('stg_inpatient_charges') }}

),

aggregated as (

    select
        provider_ccn,
        release_year,

        count(distinct drg_code)                 as drg_count,
        sum(discharges)                          as total_discharges,

        sum(discharges * avg_submitted_charge)   as total_submitted_charges,
        sum(discharges * avg_medicare_payment)   as total_medicare_payment,
        sum(discharges * avg_total_payment)      as total_payment,

        div0(sum(discharges * avg_submitted_charge),
             sum(discharges))                    as weighted_avg_charge,
        div0(sum(discharges * avg_medicare_payment),
             sum(discharges))                    as weighted_avg_medicare_payment,

        div0(sum(discharges * avg_medicare_payment),
             sum(discharges * avg_submitted_charge)) as payment_to_charge_ratio,

        avg(avg_submitted_charge)                as unweighted_avg_charge

    from charges
    group by provider_ccn, release_year

)

select * from aggregated
"""

FILES["models/intermediate/_intermediate_models.yml"] = """version: 2

models:
  - name: int_quality_measures
    description: >
      All non-HCAHPS quality measures unioned into a single fact table.
      One row per provider per measure per vintage.
    columns:
      - name: quality_measure_key
        description: Surrogate key over provider, measure, and vintage.
        data_tests:
          - unique
          - not_null
      - name: provider_ccn
        data_tests: [not_null]
      - name: measure_domain
        data_tests:
          - accepted_values:
              values:
                - 'Complications & Deaths'
                - 'Unplanned Visits'
                - 'Healthcare-Associated Infections'
                - 'Spending'

  - name: int_provider_costs
    description: >
      Inpatient charges aggregated to provider-year using
      discharge-weighted averages.
    columns:
      - name: provider_ccn
        data_tests: [not_null]
      - name: payment_to_charge_ratio
        description: Medicare payment as a share of billed charges.
        data_tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1
              where: "payment_to_charge_ratio is not null"
"""

for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote {path}")