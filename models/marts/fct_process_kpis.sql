-- Process KPIs mart
-- Grain: one row per month × category
-- Powers cycle time, DPO, and 3-way match trend charts

with pos as (
    select * from {{ ref('stg_purchase_orders') }}
),

invoices as (
    select * from {{ ref('stg_invoices') }}
),

-- PO-side metrics: cycle time and on-time delivery
po_metrics as (
    select
        po_month_start,
        category,
        count(*)                                       as po_count,
        avg(req_to_po_days)                            as avg_req_to_po_days,
        avg(delivery_slip_days)                        as avg_delivery_slip_days,
        sum(case when is_on_time_delivery then 1 else 0 end) as on_time_deliveries,
        sum(case when is_on_time_delivery is not null then 1 else 0 end) as deliveries_with_data
    from pos
    group by po_month_start, category
),

-- Invoice-side metrics: DPO, 3-way match, on-time payment
-- Join back to PO to get the category and month
invoice_metrics as (
    select
        p.po_month_start,
        p.category,
        count(*)                                       as invoice_count,
        avg(i.days_to_pay)                             as avg_days_to_pay,     -- DPO proxy
        sum(case when i.is_three_way_matched then 1 else 0 end) as matched_invoices,
        sum(case when i.is_paid_on_time then 1 else 0 end)      as on_time_payments,
        sum(case when i.is_paid_on_time is not null then 1 else 0 end) as invoices_with_payment_data
    from invoices i
    inner join pos p on i.po_id = p.po_id
    group by p.po_month_start, p.category
),

final as (
    select
        coalesce(pm.po_month_start, im.po_month_start) as month,
        coalesce(pm.category,       im.category)       as category,

        -- PO throughput and cycle time
        coalesce(pm.po_count, 0)                       as po_count,
        pm.avg_req_to_po_days                          as avg_req_to_po_cycle_days,
        pm.avg_delivery_slip_days,
        div0(pm.on_time_deliveries, pm.deliveries_with_data) as on_time_delivery_rate,

        -- Invoice / payment metrics
        coalesce(im.invoice_count, 0)                  as invoice_count,
        im.avg_days_to_pay                             as avg_days_payable_outstanding,
        div0(im.matched_invoices,  im.invoice_count)   as three_way_match_rate,
        div0(im.on_time_payments,  im.invoices_with_payment_data) as on_time_payment_rate

    from po_metrics pm
    full outer join invoice_metrics im
        on pm.po_month_start = im.po_month_start
        and pm.category      = im.category
)

select * from final