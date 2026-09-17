-- Staging model for vendors
-- Light cleanup + type casting, no business logic
-- Materialized as a view (see dbt_project.yml)

with source as (
    select * from {{ source('procureiq_raw', 'vendors') }}
),

renamed as (
    select
        -- IDs
        vendor_id,

        -- Attributes
        vendor_name,
        category,
        region,
        country,
        diversity_classification,

        -- Flags
        preferred_status              as is_preferred,
        is_strategic,

        -- Metrics
        risk_score,

        -- Risk bucket - derived for easier grouping in dashboards
        case
            when risk_score >= 75 then 'High'
            when risk_score >= 40 then 'Medium'
            else 'Low'
        end                           as risk_tier,

        -- Dates
        onboarded_date,

        -- Vendor tenure in years - useful for reporting
        datediff('year', onboarded_date, current_date()) as vendor_tenure_years

    from source
)

select * from renamed