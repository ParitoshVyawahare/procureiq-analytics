-- Monthly spend trend mart
-- Grain: month × category × spend_type (Direct/Indirect)
-- Powers YoY spend chart, Q4 seasonality chart, category trend chart

with spend as (
    select * from {{ ref('fct_spend') }}
),

monthly as (
    select
        po_month_start                as month,
        po_year                       as year,
        po_quarter                    as quarter,
        category,
        spend_type,

        count(distinct po_id)         as po_count,
        sum(po_amount)                as total_spend,
        avg(po_amount)                as avg_po_amount,
        count(distinct vendor_id)     as unique_vendors,

        sum(case when is_maverick then po_amount else 0 end) as maverick_spend

    from spend
    group by all
),

with_yoy as (
    -- Window function to get prior-year spend for same month × category × spend_type
    select
        m.*,

        -- Prior year spend (12 months back)
        lag(total_spend, 12) over (
            partition by category, spend_type
            order by month
        ) as prior_year_spend

    from monthly m
),

final as (
    select
        month,
        year,
        quarter,
        category,
        spend_type,

        po_count,
        total_spend,
        avg_po_amount,
        unique_vendors,
        maverick_spend,

        prior_year_spend,

        -- YoY growth
        total_spend - prior_year_spend                            as yoy_spend_change,
        div0(total_spend - prior_year_spend, prior_year_spend)    as yoy_spend_change_pct

    from with_yoy
)

select * from final