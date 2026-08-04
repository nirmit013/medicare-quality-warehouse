{{
    config(materialized='view')
}}

/*
    One row per provider per vintage.

    CMS renamed several columns between the 2023 and 2026 snapshots:
        CITY          -> CITY_TOWN
        COUNTY_NAME   -> COUNTY_PARISH
        PHONE_NUMBER  -> TELEPHONE_NUMBER

    Stacking the vintages produced both sets of columns, each populated
    only for the years that used that name. COALESCE resolves them back
    into one field per attribute.
*/

with source as (

    select * from {{ source('cms_raw', 'hospital_general_info') }}

),

renamed as (

    select
        {{ clean_ccn('facility_id') }}          as provider_ccn,
        trim(facility_name)                      as provider_name,
        trim(address)                            as address,
        coalesce(trim(city), trim(city_town))    as city,
        trim(state)                              as state,
        trim(zip_code)                           as zip_code,
        coalesce(trim(county_name),
                 trim(county_parish))            as county,
        coalesce(trim(phone_number),
                 trim(telephone_number))         as phone_number,

        trim(hospital_type)                      as hospital_type,
        trim(hospital_ownership)                 as hospital_ownership,
        trim(emergency_services)                 as emergency_services,

        try_cast(hospital_overall_rating as int) as overall_star_rating,

        to_date(vintage, 'YYYY-MM-DD')           as vintage_date,
        vintage                                  as vintage

    from source
    where facility_id is not null

)

select * from renamed
