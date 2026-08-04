"""
Load CMS Care Compare CSVs into Snowflake RAW schema.
======================================================
Reads every vintage of each file type, stacks them with a VINTAGE column,
sanitizes headers, and writes one table per file type.

Setup:
    pip install "snowflake-connector-python[pandas]"

Then set your password as an environment variable so it stays out of Git:
    $env:SNOWFLAKE_PASSWORD = "your-password"     (PowerShell, this session)

Run:
    python load_to_snowflake.py
"""

import os
import re
import glob
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

# ---------------------------------------------------------------- config

ACCOUNT = "OHOVNNY-IL84253"
USER = os.environ.get("SNOWFLAKE_USER") or "REPLACE_WITH_YOUR_USERNAME"
PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD")

DATABASE = "MEDICARE_QUALITY"
SCHEMA = "RAW"
WAREHOUSE = "COMPUTE_WH"
ROLE = "ACCOUNTADMIN"

SELECTED = os.path.join("data", "selected")

# file name -> Snowflake table name
TABLE_MAP = {
    "Hospital_General_Information.csv": "HOSPITAL_GENERAL_INFO",
    "HCAHPS-Hospital.csv": "HCAHPS",
    "Complications_and_Deaths-Hospital.csv": "COMPLICATIONS_DEATHS",
    "Healthcare_Associated_Infections-Hospital.csv": "INFECTIONS",
    "Unplanned_Hospital_Visits-Hospital.csv": "UNPLANNED_VISITS",
    "Medicare_Hospital_Spending_Per_Patient-Hospital.csv": "SPENDING_PER_PATIENT",
    "Footnote_Crosswalk.csv": "FOOTNOTE_CROSSWALK",
}


def clean_column(name):
    """
    CMS headers contain spaces, slashes, and punctuation. Normalize to
    UPPER_SNAKE so dbt models don't need quoted identifiers everywhere.
    """
    name = str(name).strip()
    name = re.sub(r"[^\w\s]", " ", name)      # punctuation -> space
    name = re.sub(r"\s+", "_", name.strip())  # spaces -> underscore
    name = re.sub(r"_+", "_", name)           # collapse repeats
    name = name.upper().strip("_")
    if name and name[0].isdigit():            # can't start with a digit
        name = "C_" + name
    return name or "UNNAMED"


def load_csv(path):
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode {path}")


def build_table(filename):
    """Stack every vintage of one file type into a single DataFrame."""
    frames = []
    vintages = sorted(
        d for d in os.listdir(SELECTED) if os.path.isdir(os.path.join(SELECTED, d))
    )

    for vintage in vintages:
        path = os.path.join(SELECTED, vintage, filename)
        if not os.path.exists(path):
            print(f"    {vintage}: not present, skipped")
            continue

        df = load_csv(path)
        df.columns = [clean_column(c) for c in df.columns]

        # dedupe any column names that collided after cleaning
        seen = {}
        cols = []
        for c in df.columns:
            if c in seen:
                seen[c] += 1
                cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                cols.append(c)
        df.columns = cols

        df["VINTAGE"] = vintage
        frames.append(df)
        print(f"    {vintage}: {len(df):,} rows, {len(df.columns)} cols")

    if not frames:
        return None

    # concat unions the columns - a field missing in one vintage becomes NULL
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return combined


def main():
    if not PASSWORD:
        print("SNOWFLAKE_PASSWORD is not set.")
        print('PowerShell:  $env:SNOWFLAKE_PASSWORD = "your-password"')
        return

    if USER.startswith("REPLACE"):
        print("Set your username at the top of this script, or:")
        print('PowerShell:  $env:SNOWFLAKE_USER = "your-username"')
        return

    print(f"Connecting to {ACCOUNT} as {USER} ...")
    conn = snowflake.connector.connect(
        account=ACCOUNT,
        user=USER,
        password=PASSWORD,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
        role=ROLE,
    )
    print("Connected.\n")

    summary = []

    try:
        for filename, table in TABLE_MAP.items():
            print(f"{table}")
            df = build_table(filename)

            if df is None:
                print("    no files found, skipped\n")
                continue

            success, nchunks, nrows, _ = write_pandas(
                conn,
                df,
                table_name=table,
                database=DATABASE,
                schema=SCHEMA,
                auto_create_table=True,
                overwrite=True,
                quote_identifiers=False,
            )

            status = "ok" if success else "FAILED"
            print(f"    -> {table}: {nrows:,} rows loaded [{status}]\n")
            summary.append((table, nrows, len(df.columns)))

        print("=" * 55)
        print("LOADED")
        print("=" * 55)
        total = 0
        for table, nrows, ncols in summary:
            print(f"{table:<28} {nrows:>10,} rows  {ncols:>3} cols")
            total += nrows
        print("-" * 55)
        print(f"{'TOTAL':<28} {total:>10,} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
