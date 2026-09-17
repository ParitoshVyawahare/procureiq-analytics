-- Contract compliance mart
-- One row per department + category, with maverick vs on-contract breakdown
-- Powers governance dashboards and the "18% maverick, worst in Marketing" story

with spend as (
    select * from {{ ref('fct_spend') }}
),

by_dept_category as (
    select
        requester_dept,
        category,
        spend_type,

        -- Counts
        count(distinct po_id)                                  as total_pos,
        sum(case when is_maverick then 1 else 0 end)           as maverick_pos,
        sum(case when not is_maverick then 1 else 0 end)       as on_contract_pos,

        -- Amounts
        sum(po_amount)                                         as total_spend,
        sum(case when is_maverick then po_amount else 0 end)   as maverick_spend,
        sum(case when not is_maverick then po_amount else 0 end) as on_contract_spend

    from spend
    group by all
),

final as (
    select
        requester_dept,
        category,
        spend_type,

        total_pos,
        maverick_pos,
        on_contract_pos,

        total_spend,
        maverick_spend,
        on_contract_spend,

        -- Compliance rates
        div0(on_contract_pos,   total_pos)   as contract_compliance_rate_pct,
        div0(maverick_pos,      total_pos)   as maverick_rate_pct,
        div0(maverick_spend,    total_spend) as maverick_spend_share_pct

    from by_dept_category
)

select * from final