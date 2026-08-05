/*
    Does charging more buy better outcomes?

    Providers are split into charge quartiles by discharge-weighted
    average submitted charge, then compared on CMS quality measures.
    Run with: dbt compile --select cost_vs_quality_findings
*/

-- Headline: quality across charge quartiles
select
    charge_quartile,
    count(*)                                   as hospitals,
    round(avg(weighted_avg_charge))            as avg_charge,
    round(avg(overall_star_rating), 2)         as avg_stars,
    round(avg(avg_readmission_rate), 2)        as avg_readmission,
    round(avg(avg_mortality_rate), 2)          as avg_mortality,
    round(avg(medicare_spending_ratio), 3)     as avg_spending_ratio
from {{ ref('mart_cost_vs_quality') }}
group by charge_quartile
order by charge_quartile;