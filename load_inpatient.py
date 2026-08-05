"""Load Project 1 inpatient charge CSVs into Snowflake RAW."""
import os, re, glob, warnings
warnings.filterwarnings("ignore")
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

ACCOUNT = "OHOVNNY-IL84253"
USER = os.environ.get("SNOWFLAKE_USER")
PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD")
INPATIENT_DIR = r"D:\medicare-project\data\raw"

def clean(c):
    c = re.sub(r"[^\w\s]", " ", str(c).strip())
    c = re.sub(r"\s+", "_", c.strip())
    return re.sub(r"_+", "_", c).upper().strip("_")

frames = []
for path in sorted(glob.glob(os.path.join(INPATIENT_DIR, "*.csv"))):
    year = re.search(r"(20\d{2})", os.path.basename(path)).group(1)
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [clean(c) for c in df.columns]
    df["RELEASE_YEAR"] = year
    frames.append(df)
    print(f"  {year}: {len(df):,} rows")

combined = pd.concat(frames, ignore_index=True, sort=False)
print(f"\nTotal: {len(combined):,} rows")

conn = snowflake.connector.connect(
    account=ACCOUNT, user=USER, password=PASSWORD,
    warehouse="COMPUTE_WH", database="MEDICARE_QUALITY",
    schema="RAW", role="ACCOUNTADMIN")

ok, _, n, _ = write_pandas(conn, combined, table_name="INPATIENT_CHARGES",
                           database="MEDICARE_QUALITY", schema="RAW",
                           auto_create_table=True, overwrite=True,
                           quote_identifiers=False)
print(f"Loaded {n:,} rows [{'ok' if ok else 'FAILED'}]")
conn.close()