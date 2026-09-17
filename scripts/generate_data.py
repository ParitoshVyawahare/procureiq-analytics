"""
ProcureIQ - Synthetic Procurement Data Generator
=================================================
Generates 4 CSVs: vendors, contracts, purchase_orders, invoices

Design goals (patterns intentionally baked in):
  1. Category concentration (Pareto) - top 3 categories = ~60% spend
  2. Vendor concentration - some categories dominated by 1-2 vendors
  3. Maverick spend - ~18% of POs off-contract, skewed to Marketing/R&D
  4. Problem vendors - ~8 vendors with rising risk + late payments
  5. Q4 seasonality - budget-flush spike
  6. Payment behavior variance - most Net 30, one cluster chronically late
  7. Savings realization gap - realized ~65-75% of negotiated
  8. YoY growth - 2025 spend ~15% higher than 2024
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

# Reproducibility - same seed = same data every run
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# CONFIG - the "shape" of the company
# =============================================================================

CATEGORIES = [
    # (name, share_of_spend, is_direct) - shares sum to 1.0
    ("IT Services",           0.22, False),   # top 3 = ~60%
    ("Professional Services", 0.20, False),
    ("Raw Materials",         0.18, True),
    ("Logistics",             0.10, True),
    ("MRO",                   0.08, True),    # tail spend candidate
    ("Marketing",             0.07, False),   # maverick spend hotspot
    ("Capital Equipment",     0.06, True),
    ("Facilities",            0.05, False),
    ("Travel",                0.02, False),
    ("Office Supplies",       0.02, False),   # tail spend candidate
]

DEPARTMENTS = [
    "Engineering", "Operations", "Manufacturing", "IT", "Finance",
    "HR", "Marketing", "Sales", "R&D", "Legal", "Facilities"
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]
COUNTRIES_BY_REGION = {
    "North America": ["USA", "Canada", "Mexico"],
    "Europe":        ["Germany", "UK", "France", "Netherlands", "Italy"],
    "Asia Pacific":  ["China", "India", "Japan", "Singapore", "Australia"],
    "Latin America": ["Brazil", "Chile", "Argentina"],
}

DIVERSITY_CLASSIFICATIONS = [
    ("None",              0.78),
    ("Minority-Owned",    0.08),
    ("Women-Owned",       0.09),
    ("Veteran-Owned",     0.03),
    ("Small Business",    0.02),
]

PAYMENT_TERMS_OPTIONS = ["Net 30", "Net 45", "Net 60", "Net 15"]

NUM_VENDORS = 500
NUM_POS = 5500
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)

# =============================================================================
# 1. VENDORS
# =============================================================================

def generate_vendors():
    print("Generating vendors...")
    vendors = []

    # Weighted category assignment - matches spend shares roughly
    cat_names = [c[0] for c in CATEGORIES]
    cat_weights = [c[1] for c in CATEGORIES]

    for i in range(1, NUM_VENDORS + 1):
        category = random.choices(cat_names, weights=cat_weights, k=1)[0]
        region = random.choice(REGIONS)
        country = random.choice(COUNTRIES_BY_REGION[region])

        # Diversity classification - weighted
        div_names = [d[0] for d in DIVERSITY_CLASSIFICATIONS]
        div_weights = [d[1] for d in DIVERSITY_CLASSIFICATIONS]
        diversity = random.choices(div_names, weights=div_weights, k=1)[0]

        # ~15% preferred vendors
        preferred = random.random() < 0.15

        # ~10% strategic (usually overlap with preferred but not always)
        strategic = random.random() < 0.10

        # Risk score 1-100, most vendors low-risk (right-skewed)
        risk_score = int(np.clip(np.random.beta(2, 5) * 100, 1, 100))

        vendors.append({
            "vendor_id": f"V{i:05d}",
            "vendor_name": fake.company(),
            "category": category,
            "region": region,
            "country": country,
            "preferred_status": preferred,
            "is_strategic": strategic,
            "diversity_classification": diversity,
            "risk_score": risk_score,
            "onboarded_date": fake.date_between(
                start_date=datetime(2018, 1, 1),
                end_date=datetime(2023, 12, 31)
            ),
        })

    # PROBLEM VENDORS - bump risk score on 8 specific vendors
    # We'll reference these later for late payments
    problem_vendor_ids = [f"V{i:05d}" for i in random.sample(range(1, NUM_VENDORS + 1), 8)]
    for v in vendors:
        if v["vendor_id"] in problem_vendor_ids:
            v["risk_score"] = random.randint(75, 95)

    df = pd.DataFrame(vendors)
    df.to_csv(OUTPUT_DIR / "vendors.csv", index=False)
    print(f"  -> {len(df)} vendors written")
    return df, problem_vendor_ids


# =============================================================================
# 2. CONTRACTS
# =============================================================================

def generate_contracts(vendors_df):
    print("Generating contracts...")
    contracts = []

    # 75% of vendors have at least one contract (was 60%)
    contracted_vendors = vendors_df.sample(frac=0.75, random_state=SEED)

    contract_id = 1
    for _, vendor in contracted_vendors.iterrows():
        num_contracts = random.choices([1, 1, 2, 2, 3], k=1)[0]

        for _ in range(num_contracts):
            # Widen start window and lengthen contracts so coverage
            # across 2024-2025 is more reliable
            start = fake.date_between(
                start_date=datetime(2022, 1, 1),
                end_date=datetime(2024, 6, 30)
            )
            duration_days = random.choice([730, 730, 1095, 1095, 1460])
            end = start + timedelta(days=duration_days)

            negotiated_rate = round(random.uniform(0.05, 0.25), 3)
            savings_estimate = round(random.uniform(10000, 500000), 2)

            contracts.append({
                "contract_id": f"C{contract_id:05d}",
                "vendor_id": vendor["vendor_id"],
                "start_date": start,
                "end_date": end,
                "negotiated_rate": negotiated_rate,
                "savings_estimate": savings_estimate,
                "payment_terms": random.choice(PAYMENT_TERMS_OPTIONS),
            })
            contract_id += 1

    df = pd.DataFrame(contracts)
    df.to_csv(OUTPUT_DIR / "contracts.csv", index=False)
    print(f"  -> {len(df)} contracts written")
    return df


def generate_purchase_orders(vendors_df, contracts_df):
    print("Generating purchase orders...")
    pos = []

    contract_lookup = {}
    for _, c in contracts_df.iterrows():
        contract_lookup.setdefault(c["vendor_id"], []).append(
            (c["contract_id"], c["start_date"], c["end_date"])
        )

    cat_direct = {c[0]: c[2] for c in CATEGORIES}

    # Split vendor pools by category AND by whether they have a contract
    vendors_by_cat = {}
    contracted_by_cat = {}
    for cat in [c[0] for c in CATEGORIES]:
        pool = vendors_df[vendors_df["category"] == cat]
        vendors_by_cat[cat] = pool
        contracted_by_cat[cat] = pool[pool["vendor_id"].isin(contract_lookup.keys())]

    dominant_vendor = {}
    for cat in ["IT Services", "Logistics", "Capital Equipment"]:
        pool = contracted_by_cat[cat]
        if len(pool) > 0:
            dominant_vendor[cat] = pool.sample(1, random_state=SEED).iloc[0]["vendor_id"]

    cat_names = [c[0] for c in CATEGORIES]
    cat_weights = [c[1] for c in CATEGORIES]

    for i in range(1, NUM_POS + 1):
        category = random.choices(cat_names, weights=cat_weights, k=1)[0]

        # Baseline: 82% of POs go to CONTRACTED vendors (18% maverick by design)
        # Marketing/R&D override happens after dept assignment below
        dept = random.choice(DEPARTMENTS)
        maverick_prob = 0.35 if dept in ("Marketing", "R&D") else 0.15

        # Pick vendor: mostly from contracted pool, sometimes from full pool (maverick)
        use_contracted = random.random() > maverick_prob
        pool = contracted_by_cat[category] if use_contracted else vendors_by_cat[category]
        if len(pool) == 0:
            pool = vendors_by_cat[category]
        if len(pool) == 0:
            continue

        if category in dominant_vendor and use_contracted and random.random() < 0.40:
            vendor_id = dominant_vendor[category]
        else:
            vendor_id = pool.sample(1).iloc[0]["vendor_id"]

        po_date = _weighted_po_date()

        # Amount buckets - flatter distribution to avoid over-concentration
        if category in ("Capital Equipment",):
            amount = round(np.random.lognormal(mean=10.5, sigma=1.0), 2)
        elif category in ("IT Services", "Professional Services"):
            amount = round(np.random.lognormal(mean=9.8, sigma=1.0), 2)
        elif category in ("Raw Materials", "Logistics"):
            amount = round(np.random.lognormal(mean=9.3, sigma=0.9), 2)
        else:
            amount = round(np.random.lognormal(mean=8.2, sigma=1.0), 2)

        # Contract linkage - find active contract for this vendor
        contract_id = None
        if use_contracted:
            vendor_contracts = contract_lookup.get(vendor_id, [])
            po_date_only = po_date.date() if hasattr(po_date, "date") else po_date
            active = [
                cid for cid, s, e in vendor_contracts
                if s <= po_date_only <= e
            ]
            if active:
                contract_id = random.choice(active)

        requisition_date = po_date - timedelta(days=random.randint(1, 14))
        expected_delivery = po_date + timedelta(days=random.randint(7, 45))
        delivery_slip = int(np.random.normal(loc=2, scale=5))
        actual_delivery = expected_delivery + timedelta(days=delivery_slip)

        status = random.choices(
            ["Closed", "Closed", "Closed", "Closed", "Open", "Cancelled"],
            k=1
        )[0]

        pos.append({
            "po_id": f"PO{i:06d}",
            "vendor_id": vendor_id,
            "requester_dept": dept,
            "category": category,
            "spend_type": "Direct" if cat_direct[category] else "Indirect",
            "amount": amount,
            "requisition_date": requisition_date.date(),
            "po_date": po_date.date(),
            "expected_delivery_date": expected_delivery.date(),
            "actual_delivery_date": actual_delivery.date(),
            "status": status,
            "contract_id": contract_id,
        })

    df = pd.DataFrame(pos)
    df.to_csv(OUTPUT_DIR / "purchase_orders.csv", index=False)
    print(f"  -> {len(df)} POs written")
    return df


def _weighted_po_date():
    """Return a datetime in [START_DATE, END_DATE] with:
       - Q4 spike (budget flush)
       - Feb dip
       - YoY growth (2025 > 2024)
    """
    # 55% chance 2025, 45% chance 2024 -> ~22% YoY growth in count
    year = 2025 if random.random() < 0.55 else 2024

    # Month weights: Feb low, Q4 (Oct-Dec) high
    month_weights = {
        1: 0.08, 2: 0.05, 3: 0.08, 4: 0.08, 5: 0.08, 6: 0.08,
        7: 0.07, 8: 0.07, 9: 0.09, 10: 0.11, 11: 0.10, 12: 0.11
    }
    month = random.choices(
        list(month_weights.keys()),
        weights=list(month_weights.values()),
        k=1
    )[0]

    if month == 2:
        day = random.randint(1, 28)
    elif month in (4, 6, 9, 11):
        day = random.randint(1, 30)
    else:
        day = random.randint(1, 31)

    return datetime(year, month, day)


# =============================================================================
# 4. INVOICES
# =============================================================================

def generate_invoices(pos_df, problem_vendor_ids):
    print("Generating invoices...")
    invoices = []

    # ~90% of closed POs get invoiced (5% open POs also, small)
    invoiced_pos = pos_df[pos_df["status"] == "Closed"].sample(frac=0.95, random_state=SEED)

    invoice_id = 1
    for _, po in invoiced_pos.iterrows():
        # Invoice date: 5-30 days after PO date
        po_date = pd.to_datetime(po["po_date"])
        invoice_date = po_date + timedelta(days=random.randint(5, 30))

        # Invoice amount: usually matches PO, sometimes small variance (partial delivery, etc.)
        variance = random.choices(
            [1.0, 1.0, 1.0, 1.0, 0.95, 1.05, 0.85],
            k=1
        )[0]
        invoice_amount = round(po["amount"] * variance, 2)

        # Payment terms - inherit from contract if any, else default Net 30
        payment_terms = random.choice(PAYMENT_TERMS_OPTIONS)
        terms_days = int(payment_terms.split()[1])

        # Payment date - PROBLEM VENDORS pay late
        if po["vendor_id"] in problem_vendor_ids:
            days_to_pay = terms_days + random.randint(15, 45)
            payment_status = "Paid Late"
        else:
            # Normal distribution around terms
            days_to_pay = int(np.random.normal(loc=terms_days, scale=8))
            days_to_pay = max(days_to_pay, 5)
            if days_to_pay > terms_days + 5:
                payment_status = "Paid Late"
            else:
                payment_status = "Paid"

        payment_date = invoice_date + timedelta(days=days_to_pay)

        # Some invoices unpaid (recent ones)
        if payment_date.date() > END_DATE.date():
            payment_date = None
            payment_status = "Unpaid"

        # 3-way match status: PO + Invoice + Receipt
        # ~85% match cleanly, 10% price/qty mismatch, 5% missing receipt
        three_way = random.choices(
            ["Matched", "Matched", "Matched", "Matched", "Matched",
             "Matched", "Matched", "Matched", "Price Variance", "Missing Receipt"],
            k=1
        )[0]

        invoices.append({
            "invoice_id": f"INV{invoice_id:06d}",
            "po_id": po["po_id"],
            "vendor_id": po["vendor_id"],
            "invoice_amount": invoice_amount,
            "invoice_date": invoice_date.date(),
            "payment_status": payment_status,
            "payment_date": payment_date.date() if payment_date else None,
            "payment_terms": payment_terms,
            "three_way_match_status": three_way,
        })
        invoice_id += 1

    df = pd.DataFrame(invoices)
    df.to_csv(OUTPUT_DIR / "invoices.csv", index=False)
    print(f"  -> {len(df)} invoices written")
    return df


# =============================================================================
# SANITY CHECKS - verify patterns are actually there
# =============================================================================

def sanity_check(vendors_df, contracts_df, pos_df, invoices_df):
    print("\n" + "=" * 60)
    print("SANITY CHECKS - are the patterns actually in the data?")
    print("=" * 60)

    # 1. Category concentration
    cat_spend = pos_df.groupby("category")["amount"].sum().sort_values(ascending=False)
    top3_share = cat_spend.head(3).sum() / cat_spend.sum()
    print(f"\n[1] Top 3 categories share of spend: {top3_share:.1%} (target: ~60%)")
    print(cat_spend.head(3).to_string())

    # 2. Maverick spend
    maverick_pct = pos_df["contract_id"].isna().mean()
    print(f"\n[2] Maverick spend (POs off-contract): {maverick_pct:.1%} (target: ~20%)")
    maverick_by_dept = pos_df.assign(
        maverick=pos_df["contract_id"].isna()
    ).groupby("requester_dept")["maverick"].mean().sort_values(ascending=False)
    print("Maverick % by dept (top 5):")
    print(maverick_by_dept.head(5).to_string())

    # 3. Q4 seasonality
    pos_df["_month"] = pd.to_datetime(pos_df["po_date"]).dt.month
    monthly = pos_df.groupby("_month")["amount"].sum()
    q4_share = monthly.loc[[10, 11, 12]].sum() / monthly.sum()
    print(f"\n[3] Q4 share of annual spend: {q4_share:.1%} (target: ~32%, baseline would be 25%)")

    # 4. YoY growth
    pos_df["_year"] = pd.to_datetime(pos_df["po_date"]).dt.year
    yoy = pos_df.groupby("_year")["amount"].sum()
    growth = (yoy[2025] / yoy[2024] - 1) if 2024 in yoy and 2025 in yoy else None
    print(f"\n[4] YoY spend growth 2024->2025: {growth:.1%} (target: ~15-25%)")

    # 5. Late payments
    late_pct = (invoices_df["payment_status"] == "Paid Late").mean()
    print(f"\n[5] Late payment rate: {late_pct:.1%}")

    # 6. 3-way match
    match_pct = (invoices_df["three_way_match_status"] == "Matched").mean()
    print(f"\n[6] 3-way match success rate: {match_pct:.1%} (target: ~80-85%)")

    # 7. Vendor concentration - top 20 vendors
    vendor_spend = pos_df.groupby("vendor_id")["amount"].sum().sort_values(ascending=False)
    top20_share = vendor_spend.head(20).sum() / vendor_spend.sum()
    print(f"\n[7] Top 20 vendors share of spend: {top20_share:.1%}")

    # Cleanup temp cols
    pos_df.drop(columns=["_month", "_year"], inplace=True, errors="ignore")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print(f"Output directory: {OUTPUT_DIR}\n")

    vendors_df, problem_vendor_ids = generate_vendors()
    contracts_df = generate_contracts(vendors_df)
    pos_df = generate_purchase_orders(vendors_df, contracts_df)
    invoices_df = generate_invoices(pos_df, problem_vendor_ids)

    sanity_check(vendors_df, contracts_df, pos_df, invoices_df)

    print("\n" + "=" * 60)
    print("DONE. Files written to:", OUTPUT_DIR)
    print("=" * 60)