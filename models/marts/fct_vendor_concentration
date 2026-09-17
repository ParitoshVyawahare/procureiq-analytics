-- Vendor-level spend rollup with concentration analysis
-- Powers "top vendors as % of spend", "tail spend consolidation", vendor scorecards

with spend as (
    select * from {{ ref('fct_spend') }}
),

vendor_spend as (
    select
        vendor_id,
        vendor_name,
        vendor_region,
        vendor_country,
        vendor_is_preferred,
        vendor_is_strategic,
        vendor_diversity_classification,
        vendor_risk_tier,
        vendor_risk_score,

        -- Aggregates
        count(distinct po_id)             as po_count,
        sum(po_amount)                    as total_spend,
        avg(po_amount)                    as avg_po_amount,
        min(po_date)                      as first_po_date,
        max(po_date)                      as last_po_date,

        -- Maverick share for this vendor
        sum(case when is_maverick then po_amount else 0 end) as maverick_spend,
        sum(case when is_maverick then 1 else 0 end)         as maverick_po_count

    from spend
    group by all
),

with_share as (
    select
        vs.*,

        -- Share of total spend (window function over all vendors)
        vs.total_spend / sum(vs.total_spend) over () as spend_share_pct,

        -- Rank vendors by spend (1 = highest)
        row_number() over (order by vs.total_spend desc) as spend_rank

    from vendor_spend vs
),

final as (
    select
        *,

        -- Concentration tiers - classic procurement segmentation
        case
            when spend_rank <= 20   then 'Top 20'
            when spend_rank <= 100  then 'Top 100'
            else 'Tail'
        end as spend_tier,

        -- Cumulative share running total - useful for Pareto analysis
        sum(spend_share_pct) over (order by spend_rank) as cumulative_spend_share_pct

    from with_share
)

select * from final