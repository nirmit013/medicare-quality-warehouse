{{
    config(materialized='table')
}}

/*
    The analytical question: do hospitals that charge more deliver
    better outcomes?

    Joins discharge-weighted inpatient charges to CMS quality ratings,
    readmission and mortality rates, Medicare spending efficiency, and
    patient experience at provider level. Uses the latest available
    charge year against the most recent quality vintage.

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

/*
    Patient experience is pivoted from HCAHPS rather than averaged.
    The measures are not comparable to each other - some are star
    ratings, some are percentages - so each is extracted by measure_id
    into its own column.
*/
patient_experience as (

    select
        provider_ccn,

        max(case when measure_id = 'H_STAR_RATING'
                 then star_rating end)                as patient_experience_stars,

        max(case when measure_id = 'H_HSP_RATING_STAR_RATING'
                 then star_rating end)                as overall_hospital_rating_stars,

        max(case when measure_id = 'H_RECMND_DY'
                 then answer_percent end)             as pct_would_recommend,

        max(completed_surveys)                        as survey_responses

    from {{ ref('stg_hcahps') }}
    where vintage = (select max(vintage) from {{ ref('stg_hcahps') }})
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

        pe.patient_experience_stars,
        pe.overall_hospital_rating_stars,
        pe.pct_would_recommend,
        pe.survey_responses,

        ntile(4) over (order by c.weighted_avg_charge)
                                                      as charge_quartile,

        c.release_year

    from costs c
    inner join providers p on c.provider_ccn = p.provider_ccn
    left join readmission r on c.provider_ccn = r.provider_ccn
    left join mortality m on c.provider_ccn = m.provider_ccn
    left join spending s on c.provider_ccn = s.provider_ccn
    left join patient_experience pe on c.provider_ccn = pe.provider_ccn

)

select * from final