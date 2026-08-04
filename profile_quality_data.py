"""
CMS Hospital Care Compare - Data Profiler
==========================================
Profiles the selected quality files across all vintages, measures provider
churn between snapshots, and checks whether CCNs join to the Project 1
inpatient charge data.

Usage:
    python profile_quality_data.py

Expects:  ./data/selected/<vintage>/*.csv
Writes:   ./docs/quality_profile.md
"""

import os
import glob
import warnings

warnings.filterwarnings("ignore")

import pandas as pd

SELECTED = os.path.join("data", "selected")
OUT_DIR = "docs"
OUT_FILE = os.path.join(OUT_DIR, "quality_profile.md")

# Path to the Project 1 inpatient CSVs - edit if yours differs
INPATIENT_DIR = r"D:\medicare-project\data\raw"

# CMS uses different header names for the provider ID depending on file and year
CCN_ALIASES = [
    "Facility ID",
    "Facility_ID",
    "Provider ID",
    "Provider_ID",
    "CMS Certification Number (CCN)",
    "Rndrng_Prvdr_CCN",
]


def find_ccn(columns):
    """Return whichever CCN alias is present in this file."""
    for alias in CCN_ALIASES:
        if alias in columns:
            return alias
    return None


def normalize_ccn(series):
    """
    CCNs are 6-character identifiers with meaningful leading zeros.
    Excel and some exports strip them, so pad back to 6 before comparing.
    """
    return (
        series.dropna()
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )


def load(path):
    """CMS files are usually UTF-8 but occasionally latin-1."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not decode {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.isdir(SELECTED):
        print(f"Not found: {SELECTED}/")
        print("Expected structure: data/selected/<vintage>/*.csv")
        return

    vintages = sorted(
        d for d in os.listdir(SELECTED) if os.path.isdir(os.path.join(SELECTED, d))
    )

    if not vintages:
        print(f"No vintage folders inside {SELECTED}/")
        return

    print(f"Found {len(vintages)} vintage(s): {', '.join(vintages)}\n")

    lines = ["# CMS Hospital Care Compare - Data Profile\n"]
    lines.append(f"Vintages profiled: {', '.join(vintages)}\n")

    ccn_sets = {}       # vintage -> set of CCNs from Hospital_General_Information
    summary_rows = []

    # ---------- per-vintage, per-file profile ----------
    for vintage in vintages:
        lines.append(f"\n## Vintage {vintage}\n")
        lines.append("| File | Rows | Cols | CCN column | Distinct CCNs | Null % (worst col) |")
        lines.append("|---|---:|---:|---|---:|---:|")

        for path in sorted(glob.glob(os.path.join(SELECTED, vintage, "*.csv"))):
            name = os.path.basename(path)
            df = load(path)

            ccn_col = find_ccn(df.columns)
            if ccn_col:
                ccns = set(normalize_ccn(df[ccn_col]).unique())
                n_ccn = len(ccns)
                if "General_Information" in name:
                    ccn_sets[vintage] = ccns
            else:
                n_ccn = 0

            # worst null percentage across columns - flags suppression-heavy files
            if len(df):
                worst_null = max(df[c].isna().sum() / len(df) * 100 for c in df.columns)
            else:
                worst_null = 0.0

            lines.append(
                f"| {name} | {len(df):,} | {len(df.columns)} | "
                f"{ccn_col or '**NONE**'} | {n_ccn:,} | {worst_null:.1f}% |"
            )

            summary_rows.append(
                {"vintage": vintage, "file": name, "rows": len(df), "cols": len(df.columns)}
            )
            print(f"  {vintage} / {name}: {len(df):,} rows x {len(df.columns)} cols")

    # ---------- provider churn across vintages ----------
    if len(ccn_sets) > 1:
        lines.append("\n\n## Provider churn across vintages\n")
        lines.append(
            "Change in the provider roster between snapshots. This is what makes "
            "a slowly-changing dimension worth building.\n"
        )
        lines.append("| Vintage | Providers | New vs prior | Dropped vs prior |")
        lines.append("|---|---:|---:|---:|")

        prev = None
        for vintage in sorted(ccn_sets):
            current = ccn_sets[vintage]
            if prev is None:
                lines.append(f"| {vintage} | {len(current):,} | - | - |")
            else:
                lines.append(
                    f"| {vintage} | {len(current):,} | "
                    f"{len(current - prev):,} | {len(prev - current):,} |"
                )
            prev = current

        stable = set.intersection(*ccn_sets.values())
        union = set.union(*ccn_sets.values())
        lines.append(f"\n- Present in **every** vintage: **{len(stable):,}**")
        lines.append(f"- Appearing in **any** vintage: **{len(union):,}**")
        lines.append(
            f"- Providers that entered or exited at some point: "
            f"**{len(union) - len(stable):,}**\n"
        )

    # ---------- join viability against Project 1 ----------
    lines.append("\n\n## Join viability with inpatient charge data\n")

    inpatient_files = sorted(glob.glob(os.path.join(INPATIENT_DIR, "*.csv")))

    if not inpatient_files:
        lines.append(
            f"Inpatient CSVs not found at `{INPATIENT_DIR}` - skipped. "
            "Edit INPATIENT_DIR at the top of this script if the path differs.\n"
        )
        print(f"\nInpatient data not found at {INPATIENT_DIR} - skipped join check.")
    elif not ccn_sets:
        lines.append("No Hospital_General_Information.csv found - skipped.\n")
    else:
        # prefer the most recent inpatient file
        ip_path = inpatient_files[-1]
        ip = load(ip_path)
        ip_ccn_col = find_ccn(ip.columns)

        if not ip_ccn_col:
            lines.append(f"No CCN column found in `{os.path.basename(ip_path)}` - skipped.\n")
        else:
            ip_ccns = set(normalize_ccn(ip[ip_ccn_col]).unique())
            latest_vintage = sorted(ccn_sets)[-1]
            cc_ccns = ccn_sets[latest_vintage]

            overlap = ip_ccns & cc_ccns
            pct = len(overlap) / len(ip_ccns) * 100 if ip_ccns else 0

            lines.append(f"Compared `{os.path.basename(ip_path)}` against vintage {latest_vintage}.\n")
            lines.append(f"- Inpatient providers: **{len(ip_ccns):,}**")
            lines.append(f"- Care Compare providers: **{len(cc_ccns):,}**")
            lines.append(f"- **Matched on CCN: {len(overlap):,} ({pct:.1f}% of inpatient)**")
            lines.append(f"- Inpatient only (no quality data): {len(ip_ccns - cc_ccns):,}")
            lines.append(f"- Care Compare only (no charge data): {len(cc_ccns - ip_ccns):,}\n")

            if pct < 80:
                lines.append(
                    "> Match rate below 80%. Check CCN formatting - leading zeros are "
                    "the usual culprit - before assuming the providers genuinely differ.\n"
                )

            print(f"\nCCN overlap: {len(overlap):,} of {len(ip_ccns):,} inpatient providers ({pct:.1f}%)")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nWritten to {OUT_FILE}")
    print("\n" + "=" * 60)
    print("RECORD THESE")
    print("=" * 60)
    for vintage in sorted(ccn_sets):
        print(f"{vintage}: {len(ccn_sets[vintage]):,} providers")


if __name__ == "__main__":
    main()
