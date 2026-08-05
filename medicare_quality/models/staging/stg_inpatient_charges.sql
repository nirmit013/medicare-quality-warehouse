{{
    config(materialized='view')
}}

/*
    Inpatient charges by provider and MS-DRG.

    The Avg_* columns are already averages across each hospital's
    discharges for that DRG, so any downstream aggregation must weight
    by discharge count. Unweighted averaging treats a hospital with 8
    discharges the same as one with 2,400 - measured at up to 44%
    distortion in behavioral health DRGs.

    Grain: one row per provider per DRG per release year.
*/

with source as (

    select * from {{ source('cms_raw', 'inpatient_charges') }}

),

renamed as (

    select
        {{ clean_ccn('rndrng_prvdr_ccn') }}              as provider_ccn,
        trim(drg_cd)                                     as drg_code,
        trim(drg_desc)                                   as drg_description,

        try_cast(tot_dschrgs as int)                     as discharges,
        try_cast(avg_submtd_cvrd_chrg as float)          as avg_submitted_charge,
        try_cast(avg_tot_pymt_amt as float)              as avg_total_payment,
        try_cast(avg_mdcr_pymt_amt as float)             as avg_medicare_payment,

        try_cast(release_year as int)                    as release_year

    from source
    where rndrng_prvdr_ccn is not null
      and try_cast(tot_dschrgs as int) > 0

)

select * from renamed