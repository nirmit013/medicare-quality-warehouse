{{
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
