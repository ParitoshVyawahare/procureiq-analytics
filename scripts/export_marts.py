"""
ProcureIQ - Export dbt marts from Snowflake to CSV
===================================================
Reads each mart table from Snowflake and writes it to data/marts/ as a CSV.
These CSVs power the Tableau dashboards (Tableau Public can't connect to Snowflake live).
Also makes the project reproducible after the Snowflake trial expires.
"""

import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# Output folder for mart CSVs
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "marts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ⚠️ Update this to match your actual dbt dev schema name
# Check Snowsight → PROCUREIQ database → find schema starting with DBT_ ending in _ANALYTICS
ANALYTICS_SCHEMA = "DBT_PARITOSH_ANALYTICS"

# All 7 marts to export
MARTS = [
    "dim_vendors",
    "fct_spend",
    "fct_spend_trend",
    "fct_vendor_concentration",
    "fct_contract_compliance",
    "fct_savings",
    "fct_process_kpis",
]


def connect():
    print("Connecting to Snowflake...")
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
    )


def export_mart(conn, table_name):
    query = f"SELECT * FROM {ANALYTICS_SCHEMA}.{table_name}"
    print(f"\nExporting {table_name}...")

    df = pd.read_sql(query, conn)

    # Lowercase column names for Tableau friendliness
    df.columns = [c.lower() for c in df.columns]

    out_path = OUTPUT_DIR / f"{table_name}.csv"
    df.to_csv(out_path, index=False)
    print(f"  ✓ {len(df):,} rows -> {out_path.name}")
    return len(df)


if __name__ == "__main__":
    conn = connect()
    try:
        total = 0
        for mart in MARTS:
            total += export_mart(conn, mart)
        print(f"\n✓ DONE - exported {total:,} rows across {len(MARTS)} marts")
        print(f"  Files in: {OUTPUT_DIR}")
    finally:
        conn.close()