/*
    Which patient-experience measures drive the decline at high-charge
    hospitals?

    Headline finding: hospitals in the top charge quartile score 18%
    worse on summary patient experience than the bottom quartile, while
    delivering 16% lower mortality. This breaks that gap down by measure.

    Result: four of the five widest gaps are communication measures -
    nurse communication (-0.86), doctor communication (-0.77), discharge
    information (-0.63), communication about medicines (-0.61).
    Cleanliness, by contrast, is among the smallest gaps (-0.37).

    The two global assessments move least: overall hospital rating
    (-0.37) and would-recommend (-0.25). Patients at expensive hospitals
    rate specific communication interactions much worse while their
    overall verdict stays largely intact.

    Run with: dbt compile --select patient_experience_breakdown
*/

with quartiles as (

    select provider_ccn, charge_quartile
    from {{ ref('mart_cost_vs_quality') }}

),

experience as (

    select *
    from {{ ref('stg_hcahps') }}
    where measure_id ilike '%STAR_RATING'
      and star_rating is not null
      and vintage = (select max(vintage) from {{ ref('stg_hcahps') }})

)

select
    e.measure_name,
    round(avg(case when q.charge_quartile = 1 then e.star_rating end), 2) as q1_lowest_charge,
    round(avg(case when q.charge_quartile = 4 then e.star_rating end), 2) as q4_highest_charge,
    round(
        avg(case when q.charge_quartile = 4 then e.star_rating end)
      - avg(case when q.charge_quartile = 1 then e.star_rating end)
    , 2)                                                                  as gap

from experience e
join quartiles q on e.provider_ccn = q.provider_ccn
group by e.measure_name
order by gap