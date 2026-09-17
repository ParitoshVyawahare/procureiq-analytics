-- Vendor dimension table
-- One row per vendor with descriptive attributes + pre-computed activity metrics
-- Serves as the "vendor" dimension in a star schema alongside fct_spend, fct_savings

with vendors as (
    select * from {{ ref('stg_vendors') }}
),

vendor_activity as (
    -- Pre-compute activity metrics per vendor so dashboards don't re-aggregate
    select
        vendor_id,
        count(distinct po_id)          as lifetime_po_count,
        sum(po_amount)                 as lifetime_spend,
        min(po_date)                   as first_po_date,
        max(po_date)                   as last_po_date,
        datediff('day', max(po_date), current_date()) as days_since_last_po
    from {{ ref('stg_purchase_orders') }}
    group by vendor_id
),

vendor_contracts as (
    -- Contract summary per vendor
    select
        vendor_id,
        count(*)                       as total_contracts,
        sum(case when is_active_contract then 1 else 0 end) as active_contracts,
        max(contract_end_date)         as latest_contract_end_date
    from {{ ref('stg_contracts') }}
    group by vendor_id
),

final as (
    select
        -- Vendor attributes
        v.vendor_id,
        v.vendor_name,
        v.category,
        v.region,
        v.country,
        v.diversity_classification,
        v.is_preferred,
        v.is_strategic,

        -- Risk
        v.risk_score,
        v.risk_tier,

        -- Tenure
        v.onboarded_date,
        v.vendor_tenure_years,

        -- Activity metrics (defaulted to 0 if vendor has no POs)
        coalesce(va.lifetime_po_count, 0)          as lifetime_po_count,
        coalesce(va.lifetime_spend,    0)          as lifetime_spend,
        va.first_po_date,
        va.last_po_date,
        va.days_since_last_po,

        -- Contract summary
        coalesce(vc.total_contracts,   0)          as total_contracts,
        coalesce(vc.active_contracts,  0)          as active_contracts,
        vc.latest_contract_end_date,

        -- Derived flags for dashboards
        case
            when va.lifetime_po_count is null then 'Inactive'
            when va.days_since_last_po > 180 then 'Dormant'
            else 'Active'
        end as vendor_activity_status,

        case
            when vc.active_contracts > 0 then true
            else false
        end as has_active_contract

    from vendors v
    left join vendor_activity  va on v.vendor_id = va.vendor_id
    left join vendor_contracts vc on v.vendor_id = vc.vendor_id
)

select * from final