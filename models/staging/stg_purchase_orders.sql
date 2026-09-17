-- Staging model for purchase_orders

with source as (
    select * from {{ source('procureiq_raw', 'purchase_orders') }}
),

renamed as (
    select
        po_id,
        vendor_id,
        contract_id,

        requester_dept,
        category,
        spend_type,                                    -- Direct / Indirect
        status                                          as po_status,

        amount                                          as po_amount,

        -- Dates
        requisition_date,
        po_date,
        expected_delivery_date,
        actual_delivery_date,

        -- Derived: is this maverick spend? (no contract linked)
        case
            when contract_id is null then true
            else false
        end                                            as is_maverick,

        -- Derived: requisition-to-PO cycle time (days)
        datediff('day', requisition_date, po_date)     as req_to_po_days,

        -- Derived: was delivery on time?
        case
            when actual_delivery_date is null then null
            when actual_delivery_date <= expected_delivery_date then true
            else false
        end                                            as is_on_time_delivery,

        -- Derived: delivery slip in days (negative = early, positive = late)
        datediff('day', expected_delivery_date, actual_delivery_date) as delivery_slip_days,

        -- Time attributes for BI slicing
        year(po_date)                                  as po_year,
        month(po_date)                                 as po_month,
        quarter(po_date)                               as po_quarter,
        date_trunc('month', po_date)                   as po_month_start

    from source
)

select * from renamed