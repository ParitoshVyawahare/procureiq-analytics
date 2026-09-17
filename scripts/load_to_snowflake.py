"""
ProcureIQ - Load CSVs to Snowflake
===================================
Reads 4 CSVs from data/raw/ and loads them into PROCUREIQ.RAW schema.
Uses write_pandas for bulk load - fast and reliable.
"""

import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

# Load credentials from .env
load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"

# Files to load: (csv filename, target table name)
FILES = [
    ("vendors.csv",         "VENDORS"),
    ("contracts.csv",       "CONTRACTS"),
    ("purchase_orders.csv", "PURCHASE_ORDERS"),
    ("invoices.csv",        "INVOICES"),
]


def connect():
    """Open a connection to Snowflake using credentials from .env"""
    print("Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )
    print(f"  Connected as {os.getenv('SNOWFLAKE_USER')} to {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}")
    return conn


def load_csv(conn, csv_name, table_name):
    """Read one CSV, push to Snowflake, return row count."""
    csv_path = DATA_DIR / csv_name
    print(f"\nLoading {csv_name} -> {table_name}")

    df = pd.read_csv(csv_path)
    print(f"  Read {len(df):,} rows from CSV")

    # Snowflake column names are uppercase - match them
    df.columns = [c.upper() for c in df.columns]

    # write_pandas handles the bulk upload
    success, num_chunks, num_rows, _ = write_pandas(
        conn=conn,
        df=df,
        table_name=table_name,
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        overwrite=True,   # Truncates the table before load
    )

    if success:
        print(f"  ✓ Loaded {num_rows:,} rows into {table_name}")
    else:
        print(f"  ✗ FAILED to load {table_name}")
    return num_rows


def verify_counts(conn):
    """Run SELECT COUNT(*) on each table to confirm."""
    print("\n" + "=" * 50)
    print("VERIFICATION - row counts in Snowflake")
    print("=" * 50)
    cursor = conn.cursor()
    for _, table in FILES:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:20s} {count:>8,} rows")
    cursor.close()


if __name__ == "__main__":
    conn = connect()
    try:
        for csv_name, table_name in FILES:
            load_csv(conn, csv_name, table_name)
        verify_counts(conn)
        print("\n✓ DONE - all data loaded to Snowflake")
    finally:
        conn.close()
        print("Connection closed.")