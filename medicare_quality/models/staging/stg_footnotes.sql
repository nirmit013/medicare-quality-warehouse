{{
    config(materialized='view')
}}

/*
    Decodes CMS footnote codes. A NULL score is not the same as a zero
    score, and the footnote explains which kind of missing it is.

    Grain is code + vintage, not code alone. CMS revised three
    definitions across snapshots, and one of them changed scope rather
    than wording: code 22 covered only Department of Defense hospitals
    in earlier releases, and was widened to include Veterans Health
    Administration hospitals later. Keying on code alone would silently
    apply the wrong definition to older data.
*/

with source as (

    select * from {{ source('cms_raw', 'footnote_crosswalk') }}

),

renamed as (

    select distinct
        trim(footnote)                  as footnote_code,
        trim(footnote_text)             as footnote_text,
        to_date(vintage, 'YYYY-MM-DD')  as vintage_date,
        vintage                         as vintage

    from source
    where footnote is not null

)

select * from renamed