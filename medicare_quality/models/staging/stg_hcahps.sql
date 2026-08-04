{{
    config(materialized='view')
}}

/*
    Patient experience survey results.

    Unlike the other measure files, HCAHPS carries a separate footnote
    column for each metric - star rating, answer percent, survey count,
    and response rate can each be suppressed independently. They are kept
    distinct here rather than collapsed, so downstream models can tell
    which specific value is missing and why.

    The measure set also shrank across vintages, from roughly 93 measures
    per provider in 2023 to 68 by 2026 as CMS retired items. That drift is
    preserved rather than filtered.
*/

with source as (

    select * from {{ source('cms_raw', 'hcahps') }}

),

renamed as (

    select
        {{ clean_ccn('facility_id') }}                   as provider_ccn,
        trim(hcahps_measure_id)                          as measure_id,
        trim(hcahps_question)                            as measure_name,
        'Patient Experience'                             as measure_domain,
        trim(hcahps_answer_description)                  as answer_description,

        try_cast(hcahps_answer_percent as float)         as answer_percent,
        try_cast(hcahps_linear_mean_value as float)      as linear_mean_value,
        try_cast(patient_survey_star_rating as int)      as star_rating,
        try_cast(number_of_completed_surveys as int)     as completed_surveys,
        try_cast(survey_response_rate_percent as float)  as response_rate_percent,

        trim(patient_survey_star_rating_footnote)        as star_rating_footnote,
        trim(hcahps_answer_percent_footnote)             as answer_percent_footnote,
        trim(number_of_completed_surveys_footnote)       as completed_surveys_footnote,
        trim(survey_response_rate_percent_footnote)      as response_rate_footnote,

        try_cast(start_date as date)                     as measurement_start,
        try_cast(end_date as date)                       as measurement_end,

        to_date(vintage, 'YYYY-MM-DD')                   as vintage_date,
        vintage                                          as vintage

    from source
    where facility_id is not null
      and hcahps_measure_id is not null

)

select * from renamed