-- Fact table: one row per purchase order
-- Denormalizes vendor + contract attributes for fast BI queries
-- This is the "atomic" spend table - every spend dashboard reads from here

with pos as (
    select * from {{ ref('stg_purchase_orders') }}
),

vendors as (
    select * from {{ ref('stg_vendors') }}
),

contracts as (
    select * from {{ ref('stg_contracts') }}
),

joined as (
    select
        -- PO grain
        pos.po_id,
        pos.po_date,
        pos.po_month_start,
        pos.po_year,
        pos.po_quarter,
        pos.po_status,

        -- Amounts
        pos.po_amount,

        -- Category / spend type
        pos.category,
        pos.spend_type,                             -- Direct / Indirect
        pos.requester_dept,

        -- Vendor attributes (denormalized for BI performance)
        pos.vendor_id,
        vendors.vendor_name,
        vendors.region                    as vendor_region,
        vendors.country                   as vendor_country,
        vendors.is_preferred              as vendor_is_preferred,
        vendors.is_strategic              as vendor_is_strategic,
        vendors.diversity_classification  as vendor_diversity_classification,
        vendors.risk_tier                 as vendor_risk_tier,
        vendors.risk_score                as vendor_risk_score,

        -- Contract attributes
        pos.contract_id,
        pos.is_maverick,
        contracts.negotiated_rate,
        contracts.savings_estimate        as contract_annual_savings_estimate,
        contracts.expiration_status       as contract_expiration_status,

        -- Cycle time
        pos.req_to_po_days,

        -- Delivery
        pos.is_on_time_delivery,
        pos.delivery_slip_days

    from pos
    left join vendors   on pos.vendor_id   = vendors.vendor_id
    left join contracts on pos.contract_id = contracts.contract_id
)

select * from joined