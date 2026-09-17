-- Staging model for invoices

with source as (
    select * from {{ source('procureiq_raw', 'invoices') }}
),

renamed as (
    select
        invoice_id,
        po_id,
        vendor_id,

        invoice_amount,
        invoice_date,
        payment_status,
        payment_date,
        payment_terms,
        three_way_match_status,

        -- Derived: extract Net X terms as a number for DPO math
        try_cast(split_part(payment_terms, ' ', 2) as integer) as payment_terms_days,

        -- Derived: days to pay (null if unpaid)
        case
            when payment_date is null then null
            else datediff('day', invoice_date, payment_date)
        end                                            as days_to_pay,

        -- Derived: was it paid on time per contract terms?
        case
            when payment_date is null then null
            when datediff('day', invoice_date, payment_date)
                 <= try_cast(split_part(payment_terms, ' ', 2) as integer) then true
            else false
        end                                            as is_paid_on_time,

        -- Derived: 3-way match success flag (boolean)
        case
            when three_way_match_status = 'Matched' then true
            else false
        end                                            as is_three_way_matched

    from source
)

select * from renamed