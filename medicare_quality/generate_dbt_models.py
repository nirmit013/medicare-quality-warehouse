"""
Generate the dbt project files for the Medicare quality warehouse.
==================================================================
Writes sources.yml, six staging models, and their tests/docs.

Run from inside the dbt project folder:
    cd D:\\medicare-quality-warehouse\\medicare_quality
    python generate_dbt_models.py

Then:
    dbt deps
    dbt run
    dbt test
"""

import os

MODELS = "models"
STAGING = os.path.join(MODELS, "staging")

FILES = {}

# ---------------------------------------------------------------- packages

FILES["packages.yml"] = """packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.1.0", "<2.0.0"]
"""

# ---------------------------------------------------------------- sources

FILES[os.path.join(STAGING, "_sources.yml")] = """version: 2

sources:
  - name: cms_raw
    description: >
      Raw CMS Hospital Care Compare files, stacked across four annual
      snapshots (2023-01-06, 2024-01-31, 2025-02-19, 2026-02-25). Loaded
      as-is with a VINTAGE column; no cleaning applied at this layer.
    database: MEDICARE_QUALITY
    schema: RAW

    tables:
      - name: hospital_general_info
        description: >
          One row per hospital per vintage. Provider attributes plus the
          CMS overall star rating. Source of the provider dimension.
        columns:
          - name: facility_id
            description: CMS Certification Number (CCN), the provider key.

      - name: hcahps
        description: >
          Patient experience survey results. One row per provider per
          HCAHPS measure per vintage.

      - name: complications_deaths
        description: >
          Mortality and complication rates. One row per provider per
          measure per vintage, with confidence intervals.

      - name: infections
        description: >
          Healthcare-associated infection standardized ratios. One row per
          provider per measure per vintage.

      - name: unplanned_visits
        description: >
          Readmission and unplanned return measures. One row per provider
          per measure per vintage.

      - name: spending_per_patient
        description: >
          Medicare Spending Per Beneficiary. CMS's own cost-efficiency
          ratio, where 1.0 is the national median.

      - name: footnote_crosswalk
        description: >
          Decodes the numeric footnote codes that explain why a measure
          was suppressed or is otherwise unavailable.
"""

# ---------------------------------------------------------------- macro

FILES[os.path.join("macros", "clean_ccn.sql")] = """{#
    CCNs are six-character identifiers with meaningful leading zeros.
    Any step that treats them as numbers strips those zeros, which
    silently breaks joins. Always normalize before comparing.
#}

{% macro clean_ccn(column_name) %}
    lpad(trim({{ column_name }}), 6, '0')
{% endmacro %}
"""

# ---------------------------------------------------------------- staging: provider

FILES[os.path.join(STAGING, "stg_provider.sql")] = """{{
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
"""

# ---------------------------------------------------------------- staging: measure files

MEASURE_MODELS = {
    "stg_complications_deaths": {
        "source": "complications_deaths",
        "domain": "Complications & Deaths",
        "extra": """        try_cast(denominator as int)             as denominator,
        try_cast(lower_estimate as float)        as lower_estimate,
        try_cast(higher_estimate as float)       as higher_estimate,
        trim(compared_to_national)               as compared_to_national,
        cast(null as int)                        as patients_returned,""",
        "note": "Risk-adjusted mortality and complication rates, with 95% confidence intervals.",
    },
    "stg_unplanned_visits": {
        "source": "unplanned_visits",
        "domain": "Unplanned Visits",
        "extra": """        try_cast(denominator as int)             as denominator,
        try_cast(lower_estimate as float)        as lower_estimate,
        try_cast(higher_estimate as float)       as higher_estimate,
        trim(compared_to_national)               as compared_to_national,
        try_cast(number_of_patients_returned as int) as patients_returned,""",
        "note": "Readmission and unplanned return measures.",
    },
    "stg_infections": {
        "source": "infections",
        "domain": "Healthcare-Associated Infections",
        "extra": """        cast(null as int)                        as denominator,
        cast(null as float)                      as lower_estimate,
        cast(null as float)                      as higher_estimate,
        trim(compared_to_national)               as compared_to_national,
        cast(null as int)                        as patients_returned,""",
        "note": "Standardized infection ratios. Values above 1.0 indicate more infections than predicted.",
    },
    "stg_spending_per_patient": {
        "source": "spending_per_patient",
        "domain": "Spending",
        "extra": """        cast(null as int)                        as denominator,
        cast(null as float)                      as lower_estimate,
        cast(null as float)                      as higher_estimate,
        cast(null as varchar)                    as compared_to_national,
        cast(null as int)                        as patients_returned,""",
        "note": "Medicare Spending Per Beneficiary ratio. 1.0 equals the national median.",
    },
}

MEASURE_TEMPLATE = """{{{{
    config(materialized='view')
}}}}

/*
    {note}

    Grain: one row per provider per measure per vintage.

    SCORE arrives as text because CMS writes 'Not Available' and
    'Not Applicable' into the same column as real values. TRY_CAST
    converts what it can and returns NULL for the rest, so suppression
    stays visible as NULL rather than silently failing the load.

    Columns not present in this source are cast as NULL so every
    staging model shares one shape and can be unioned downstream.
*/

with source as (

    select * from {{{{ source('cms_raw', '{source}') }}}}

),

renamed as (

    select
        {{{{ clean_ccn('facility_id') }}}}          as provider_ccn,
        trim(measure_id)                         as measure_id,
        trim(measure_name)                       as measure_name,
        '{domain}'                               as measure_domain,

        try_cast(score as float)                 as score,
{extra}

        trim(footnote)                           as footnote_code,
        try_cast(start_date as date)             as measurement_start,
        try_cast(end_date as date)               as measurement_end,

        to_date(vintage, 'YYYY-MM-DD')           as vintage_date,
        vintage                                  as vintage

    from source
    where facility_id is not null
      and measure_id is not null

)

select * from renamed
"""

for model, cfg in MEASURE_MODELS.items():
    FILES[os.path.join(STAGING, f"{model}.sql")] = MEASURE_TEMPLATE.format(**cfg)

# ---------------------------------------------------------------- staging: hcahps

FILES[os.path.join(STAGING, "stg_hcahps.sql")] = """{{
    config(materialized='view')
}}

/*
    Patient experience survey results.

    HCAHPS is the widest of the measure files and its measure set changed
    between vintages: roughly 93 measures per provider in 2023 falling to
    68 by 2026 as CMS retired items. That drift is preserved here rather
    than filtered, so downstream models can decide how to handle it.
*/

with source as (

    select * from {{ source('cms_raw', 'hcahps') }}

),

renamed as (

    select
        {{ clean_ccn('facility_id') }}                  as provider_ccn,
        trim(hcahps_measure_id)                          as measure_id,
        trim(hcahps_question)                            as measure_name,
        'Patient Experience'                             as measure_domain,

        try_cast(hcahps_answer_percent as float)         as answer_percent,
        try_cast(patient_survey_star_rating as int)      as star_rating,
        try_cast(number_of_completed_surveys as int)     as completed_surveys,
        try_cast(survey_response_rate_percent as float)  as response_rate_percent,

        trim(hcahps_answer_description)                  as answer_description,
        trim(footnote)                                   as footnote_code,

        try_cast(start_date as date)                     as measurement_start,
        try_cast(end_date as date)                       as measurement_end,

        to_date(vintage, 'YYYY-MM-DD')                   as vintage_date,
        vintage                                          as vintage

    from source
    where facility_id is not null

)

select * from renamed
"""

# ---------------------------------------------------------------- staging: footnotes

FILES[os.path.join(STAGING, "stg_footnotes.sql")] = """{{
    config(materialized='view')
}}

/*
    Decodes CMS footnote codes. A NULL score is not the same as a zero
    score, and the footnote explains which kind of missing it is -
    too few cases, no data submitted, or results not available.
*/

with source as (

    select * from {{ source('cms_raw', 'footnote_crosswalk') }}

),

renamed as (

    select distinct
        trim(footnote)      as footnote_code,
        trim(footnote_text) as footnote_text

    from source
    where footnote is not null

)

select * from renamed
"""

# ---------------------------------------------------------------- tests

FILES[os.path.join(STAGING, "_staging_models.yml")] = """version: 2

models:
  - name: stg_provider
    description: >
      One row per provider per vintage, with column renames across
      snapshots resolved. Feeds the provider dimension.
    columns:
      - name: provider_ccn
        description: Six-character CMS Certification Number, zero-padded.
        data_tests:
          - not_null
      - name: overall_star_rating
        description: CMS overall quality star rating, 1-5. NULL when not rated.
        data_tests:
          - dbt_utils.accepted_range:
              min_value: 1
              max_value: 5
              where: "overall_star_rating is not null"
      - name: vintage
        data_tests:
          - not_null
          - accepted_values:
              values: ['2023-01-06', '2024-01-31', '2025-02-19', '2026-02-25']
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - provider_ccn
            - vintage

  - name: stg_complications_deaths
    description: Mortality and complication measures, one row per provider-measure-vintage.
    columns:
      - name: provider_ccn
        data_tests: [not_null]
      - name: measure_id
        data_tests: [not_null]
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [provider_ccn, measure_id, vintage]

  - name: stg_unplanned_visits
    description: Readmission and unplanned return measures.
    columns:
      - name: provider_ccn
        data_tests: [not_null]
      - name: measure_id
        data_tests: [not_null]
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [provider_ccn, measure_id, vintage]

  - name: stg_infections
    description: Healthcare-associated infection standardized ratios.
    columns:
      - name: provider_ccn
        data_tests: [not_null]
      - name: measure_id
        data_tests: [not_null]

  - name: stg_spending_per_patient
    description: Medicare Spending Per Beneficiary ratio.
    columns:
      - name: provider_ccn
        data_tests: [not_null]

  - name: stg_hcahps
    description: Patient experience survey results.
    columns:
      - name: provider_ccn
        data_tests: [not_null]

  - name: stg_footnotes
    description: Footnote code lookup.
    columns:
      - name: footnote_code
        data_tests:
          - unique
          - not_null
"""

# ---------------------------------------------------------------- project config

FILES["dbt_project.yml"] = """name: 'medicare_quality'
version: '1.0.0'
config-version: 2

profile: 'medicare_quality'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  medicare_quality:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts
"""


def main():
    written = 0
    for path, content in FILES.items():
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  wrote {path}")
        written += 1

    print(f"\n{written} files written.\n")
    print("Next:")
    print("  dbt deps")
    print("  dbt run")
    print("  dbt test")


if __name__ == "__main__":
    main()
