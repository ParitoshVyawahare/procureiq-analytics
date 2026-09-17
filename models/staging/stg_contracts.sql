-- Staging model for contracts

with source as (
    select * from {{ source('procureiq_raw', 'contracts') }}
),

renamed as (
    select
        contract_id,
        vendor_id,

        start_date                                     as contract_start_date,
        end_date                                       as contract_end_date,

        negotiated_rate,                                -- discount % vs list
        savings_estimate,                               -- annual $ savings target
        payment_terms,

        -- Derived: contract length in days
        datediff('day', start_date, end_date)          as contract_duration_days,

        -- Derived: is the contract active today?
        case
            when current_date() between start_date and end_date then true
            else false
        end                                            as is_active_contract,

        -- Derived: days until expiration (negative = already expired)
        datediff('day', current_date(), end_date)      as days_until_expiration,

        -- Derived: expiration bucket for compliance dashboards
        case
            when end_date < current_date() then 'Expired'
            when datediff('day', current_date(), end_date) <= 30 then 'Expiring in 30 days'
            when datediff('day', current_date(), end_date) <= 60 then 'Expiring in 60 days'
            when datediff('day', current_date(), end_date) <= 90 then 'Expiring in 90 days'
            else 'Active'
        end                                            as expiration_status

    from source
)

select * from renamed