# CMS Hospital Care Compare - Data Profile

Vintages profiled: 2023-01-06, 2024-01-31, 2025-02-19, 2026-02-25


## Vintage 2023-01-06

| File | Rows | Cols | CCN column | Distinct CCNs | Null % (worst col) |
|---|---:|---:|---|---:|---:|
| Complications_and_Deaths-Hospital.csv | 92,112 | 18 | Facility ID | 4,848 | 54.4% |
| Footnote_Crosswalk.csv | 32 | 2 | **NONE** | 0 | 0.0% |
| HCAHPS-Hospital.csv | 450,864 | 22 | Facility ID | 4,848 | 96.2% |
| Healthcare_Associated_Infections-Hospital.csv | 174,528 | 15 | Facility ID | 4,848 | 54.7% |
| Hospital_General_Information.csv | 5,317 | 38 | Facility ID | 5,317 | 80.7% |
| Medicare_Hospital_Spending_Per_Patient-Hospital.csv | 4,676 | 14 | Facility ID | 4,676 | 63.9% |
| Unplanned_Hospital_Visits-Hospital.csv | 67,872 | 20 | Facility ID | 4,848 | 55.1% |

## Vintage 2024-01-31

| File | Rows | Cols | CCN column | Distinct CCNs | Null % (worst col) |
|---|---:|---:|---|---:|---:|
| Complications_and_Deaths-Hospital.csv | 91,428 | 18 | Facility ID | 4,812 | 53.2% |
| Footnote_Crosswalk.csv | 32 | 2 | **NONE** | 0 | 0.0% |
| HCAHPS-Hospital.csv | 447,516 | 22 | Facility ID | 4,812 | 96.2% |
| Healthcare_Associated_Infections-Hospital.csv | 173,232 | 15 | Facility ID | 4,812 | 55.1% |
| Hospital_General_Information.csv | 5,425 | 39 | Facility ID | 5,425 | 84.0% |
| Medicare_Hospital_Spending_Per_Patient-Hospital.csv | 4,640 | 14 | Facility ID | 4,640 | 64.4% |
| Unplanned_Hospital_Visits-Hospital.csv | 67,368 | 20 | Facility ID | 4,812 | 52.3% |

## Vintage 2025-02-19

| File | Rows | Cols | CCN column | Distinct CCNs | Null % (worst col) |
|---|---:|---:|---|---:|---:|
| Complications_and_Deaths-Hospital.csv | 90,611 | 18 | Facility ID | 4,769 | 53.4% |
| Footnote_Crosswalk.csv | 33 | 2 | **NONE** | 0 | 0.0% |
| HCAHPS-Hospital.csv | 443,517 | 22 | Facility ID | 4,769 | 96.1% |
| Healthcare_Associated_Infections-Hospital.csv | 171,684 | 15 | Facility ID | 4,769 | 54.0% |
| Hospital_General_Information.csv | 5,396 | 38 | Facility ID | 5,396 | 83.6% |
| Medicare_Hospital_Spending_Per_Patient-Hospital.csv | 4,605 | 14 | Facility ID | 4,605 | 63.7% |
| Unplanned_Hospital_Visits-Hospital.csv | 66,766 | 20 | Facility ID | 4,769 | 53.1% |

## Vintage 2026-02-25

| File | Rows | Cols | CCN column | Distinct CCNs | Null % (worst col) |
|---|---:|---:|---|---:|---:|
| Complications_and_Deaths-Hospital.csv | 95,780 | 18 | Facility ID | 4,789 | 53.2% |
| Footnote_Crosswalk.csv | 32 | 2 | **NONE** | 0 | 0.0% |
| HCAHPS-Hospital.csv | 325,652 | 22 | Facility ID | 4,789 | 95.6% |
| Healthcare_Associated_Infections-Hospital.csv | 172,404 | 15 | Facility ID | 4,789 | 53.7% |
| Hospital_General_Information.csv | 5,426 | 38 | Facility ID | 5,426 | 82.7% |
| Medicare_Hospital_Spending_Per_Patient-Hospital.csv | 4,625 | 14 | Facility ID | 4,625 | 61.3% |
| Unplanned_Hospital_Visits-Hospital.csv | 67,046 | 20 | Facility ID | 4,789 | 51.5% |


## Provider churn across vintages

Change in the provider roster between snapshots. This is what makes a slowly-changing dimension worth building.

| Vintage | Providers | New vs prior | Dropped vs prior |
|---|---:|---:|---:|
| 2023-01-06 | 5,317 | - | - |
| 2024-01-31 | 5,425 | 169 | 61 |
| 2025-02-19 | 5,396 | 74 | 103 |
| 2026-02-25 | 5,426 | 98 | 68 |

- Present in **every** vintage: **5,099**
- Appearing in **any** vintage: **5,658**
- Providers that entered or exited at some point: **559**



## Join viability with inpatient charge data

Compared `Medicare_IP_Hospitals_by_Provider_and_Service_2024.csv` against vintage 2026-02-25.

- Inpatient providers: **2,906**
- Care Compare providers: **5,426**
- **Matched on CCN: 2,883 (99.2% of inpatient)**
- Inpatient only (no quality data): 23
- Care Compare only (no charge data): 2,543
