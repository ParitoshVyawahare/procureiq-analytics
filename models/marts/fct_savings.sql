-- Savings realization mart
-- Grain: one row per contract
-- Compares negotiated (estimated) savings vs realized savings from actual PO volume
-- Powers the "savings leakage" story: contracts that overpromised and underdelivered

with contracts as (
    select * from {{ ref('stg_contracts') }}
),

vendors as (
    select * from {{ ref('stg_vendors') }}
),

-- Actual PO volume that flowed through each contract
contract_po_activity as (
    select
        contract_id,
        count(*)                       as pos_on_contract,
        sum(po_amount)                 as spend_on_contract
    from {{ ref('stg_purchase_orders') }}
    where contract_id is not null
    group by contract_id
),

final as (
    select
        -- Contract identifiers
        c.contract_id,
        c.vendor_id,
        v.vendor_name,
        v.category,

        -- Contract terms
        c.contract_start_date,
        c.contract_end_date,
        c.negotiated_rate,
        c.payment_terms,
        c.is_active_contract,
        c.expiration_status,

        -- Contract duration in years - used to prorate the annual savings estimate
        c.contract_duration_days / 365.0                       as contract_duration_years,

        -- Total estimated savings across the full contract life
        -- (savings_estimate is annual, so multiply by duration in years)
        c.savings_estimate * (c.contract_duration_days / 365.0) as total_estimated_savings,

        -- Actual PO activity
        coalesce(a.pos_on_contract,  0)                        as pos_on_contract,
        coalesce(a.spend_on_contract, 0)                       as spend_on_contract,

        -- Realized savings approximation:
        -- If we spent $X through the contract at a Y% discount vs list,
        -- realized savings ≈ spend × (rate / (1 - rate))
        -- i.e. spend is post-discount, we back into what we would have paid without the deal
        coalesce(a.spend_on_contract, 0) * (c.negotiated_rate / nullif(1 - c.negotiated_rate, 0))
                                                               as realized_savings,

        -- Savings realization rate
        div0(
            coalesce(a.spend_on_contract, 0) * (c.negotiated_rate / nullif(1 - c.negotiated_rate, 0)),
            c.savings_estimate * (c.contract_duration_days / 365.0)
        )                                                      as savings_realization_rate,

        -- Gap (positive = shortfall, negative = overachievement)
        (c.savings_estimate * (c.contract_duration_days / 365.0))
            - (coalesce(a.spend_on_contract, 0) * (c.negotiated_rate / nullif(1 - c.negotiated_rate, 0)))
                                                               as savings_gap,

        -- Realization tier - useful bucket for dashboards
        case
            when coalesce(a.pos_on_contract, 0) = 0 then 'Unused Contract'
            when div0(
                    coalesce(a.spend_on_contract, 0) * (c.negotiated_rate / nullif(1 - c.negotiated_rate, 0)),
                    c.savings_estimate * (c.contract_duration_days / 365.0)
                 ) >= 0.90 then 'On Track'
            when div0(
                    coalesce(a.spend_on_contract, 0) * (c.negotiated_rate / nullif(1 - c.negotiated_rate, 0)),
                    c.savings_estimate * (c.contract_duration_days / 365.0)
                 ) >= 0.50 then 'Underperforming'
            else 'Significant Shortfall'
        end                                                    as realization_tier

    from contracts c
    left join vendors              v on c.vendor_id   = v.vendor_id
    left join contract_po_activity a on c.contract_id = a.contract_id
)

select * from final