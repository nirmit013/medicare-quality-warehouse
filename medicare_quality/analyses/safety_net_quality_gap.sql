/*
    Safety-net hospitals rate lower on CMS stars at every charge level.
    Relevant to the ongoing debate over whether the composite rating
    penalizes hospitals serving sicker, poorer populations.
*/

select
    is_safety_net,
    charge_quartile,
    count(*)                            as hospitals,
    round(avg(weighted_avg_charge))     as avg_charge,
    round(avg(overall_star_rating), 2)  as avg_stars
from {{ ref('mart_cost_vs_quality') }}
group by is_safety_net, charge_quartile
order by is_safety_net, charge_quartile;