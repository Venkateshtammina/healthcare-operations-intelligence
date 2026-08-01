# Power BI Dashboard Build Guide

## 1. Create the database views

From the project root in PowerShell:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -W -d healthcare_operations -f "sql\power_bi_views.sql"
```

Expected result:

- Hospital dimension rows: 2,906
- DRG dimension rows: 540
- Fact rows: 145,879
- Total discharges: 4,952,481

## 2. Connect Power BI Desktop to PostgreSQL

1. Open Power BI Desktop.
2. Select **Get data → PostgreSQL database**.
3. Enter server `localhost:5432`.
4. Enter database `healthcare_operations`.
5. Select **Import** mode.
6. Sign in with database username `postgres` and the local PostgreSQL password.
7. Select these views from the `healthcare_analytics` schema:
   - `vw_fact_hospital_drg`
   - `vw_dim_hospital`
   - `vw_dim_drg`
8. Select **Load**.

Import mode is suitable for the current data size and gives responsive portfolio demonstrations.

## 3. Configure the model

Rename the tables:

- `vw_fact_hospital_drg` → `Fact_Hospital_DRG`
- `vw_dim_hospital` → `Dim_Hospital`
- `vw_dim_drg` → `Dim_DRG`

Create these relationships in Model view:

| From | Cardinality | To | Cross-filter direction |
|---|---:|---|---|
| `Dim_Hospital[provider_ccn]` | One-to-many | `Fact_Hospital_DRG[provider_ccn]` | Single |
| `Dim_DRG[drg_code]` | One-to-many | `Fact_Hospital_DRG[drg_code]` | Single |

Confirm that both relationships are active. Do not create additional relationships between the two dimensions.

Hide technical fields from report view when appropriate:

- `Fact_Hospital_DRG[service_record_id]`
- Fact-table copies of `provider_ccn` and `drg_code`
- Dimension FIPS and RUCA codes if only descriptions are used

## 4. Add measures

Create the measures listed in `dashboard/DAX_measures.md`. Use the documented number formats.

Never use a simple average of the three average financial columns for executive comparisons. Use the discharge-weighted measures.

## 5. Global report design

Use a restrained healthcare-oriented theme:

- Dark blue: `#1F4E78`
- Medium blue: `#4C78A8`
- Teal: `#2A9D8F`
- Orange highlight: `#F28E2B`
- Light background: `#F5F7FA`
- Dark text: `#263238`

Add synchronized slicers for:

- `Dim_Hospital[provider_state_abbreviation]`
- `Dim_Hospital[provider_name]`
- `Dim_DRG[drg_label]`
- `Dim_Hospital[rural_urban_group]`

Keep chart titles explicit about submitted charges versus payments.

## Page 1: Executive Overview

Business purpose: summarize portfolio scale, major demand sources, and geographic concentration.

Recommended visuals:

1. KPI cards:
   - Total Hospitals
   - Total Discharges
   - Estimated Total Payments
   - Weighted Avg Submitted Charge
   - Weighted Avg Total Payment
   - Weighted Avg Payment Gap
2. Horizontal bar chart: top 10 hospitals by Total Discharges.
3. Horizontal bar chart: top 10 DRGs by Total Discharges.
4. Filled map: state by Total Discharges.
5. Slicers across the top or in a collapsible left panel.

Decision impact: directs attention toward the providers, services, and states handling the most inpatient volume.

## Page 2: Financial Performance

Business purpose: compare submitted charges with payment amounts and identify records requiring deeper review.

Recommended visuals:

1. KPI cards:
   - Estimated Submitted Charges
   - Estimated Total Payments
   - Estimated Medicare Payments
   - Total Payment Coverage %
   - Medicare Coverage %
   - Aggregate Charge to Payment Ratio
2. Clustered bar chart by state:
   - Weighted Avg Submitted Charge
   - Weighted Avg Total Payment
   - Weighted Avg Medicare Payment
3. Scatter plot:
   - X-axis: Total Discharges
   - Y-axis: Weighted Avg Submitted Charge
   - Size: Estimated Total Payments
   - Details: provider name
4. Financial review table:
   - Hospital
   - State
   - DRG
   - Total Discharges
   - Weighted Avg Payment Gap
   - Total Payment Coverage %
   - Aggregate Charge to Payment Ratio
5. Conditional formatting on ratios and gaps.

Interpretation warning: high gaps or ratios may warrant investigation but do not independently prove inefficiency.

## Page 3: Operational Performance

Business purpose: compare service volume, provider rankings, geographic benchmarks, and rural/urban patterns.

Recommended visuals:

1. KPI cards:
   - Total Discharges
   - Total Hospitals
   - Total DRGs
   - Average Discharges per Hospital
2. Ranked hospital table:
   - Hospital Discharge Rank
   - Hospital
   - State
   - Total Discharges
   - Total DRGs
3. DRG ranking bar chart using DRG Discharge Rank.
4. Rural/urban clustered chart:
   - Total Discharges
   - Weighted Avg Total Payment
5. State benchmark matrix:
   - Hospital
   - Weighted Avg Submitted Charge
   - State Weighted Avg Submitted Charge
   - Difference from State Weighted Charge %
6. Drill-through page or tooltip showing hospital-level DRG mix.

Decision impact: supports capacity prioritization and identifies providers whose charge patterns differ from their state benchmark.

## Page 4: Forecasting

Business purpose: show a short-term external inpatient-demand indicator using
CDC RESP-NET COVID-NET observed weekly hospitalization rates.

Import these CSV files with **Home → Get data → Text/CSV**:

- `data/processed/analysis_outputs/forecast_dashboard_data.csv`
- `data/processed/analysis_outputs/forecast_model_metrics.csv`

Rename the tables:

- `forecast_dashboard_data` → `Forecast_Timeline`
- `forecast_model_metrics` → `Forecast_Model_Metrics`

Set `Forecast_Timeline[Week_Ending_Date]` to Date and all rate/metric fields to
Decimal number. Do not create relationships between these tables and the CMS
hospital model because the populations and grains differ.

Recommended visuals:

1. Line chart with date on the X-axis and actual and forecast rates as values.
2. Lower and upper approximate 95% interval lines, or native error bars when available.
3. Cards for selected model, holdout MAE, RMSE, and MAPE.
4. Horizontal bar chart comparing model RMSE values.
5. Forecast table with date, point forecast, lower bound, and upper bound.
6. Text box with the operational interpretation and limitations.

The current selected model is a recent 156-week autoregression with lags 1–4
and 52. The 12-week point forecast suggests a modest rise through mid-September
2026 followed by a decline. Approximate intervals are wide and include zero, so
management should monitor actual admissions and retain flexible capacity rather
than treat the point forecast as a commitment.

RESP-NET is a surveillance catchment dataset and is not the same population as
the CMS hospital-DRG dataset. Rates are preliminary and may be revised.

## 6. Drill-through configuration

Create a **Hospital Detail** drill-through page using `provider_ccn` as the drill-through field. Include:

- Hospital name and location
- Total discharges
- Weighted financial KPIs
- Top DRGs by volume
- DRG charge/payment comparison
- Difference from state benchmark

Use CCN as the technical drill-through key because hospital names are not guaranteed to be globally unique.

## 7. Validation checklist

With no slicers selected, confirm:

- Total Hospitals = 2,906
- Total DRGs = 540
- Total Discharges = 4,952,481
- State totals reconcile to the national total
- Hospital and DRG selections change every applicable visual
- Currency measures are not displayed as revenue
- Coverage measures are percentages
- No forecasting result is shown without a real dated dataset

Save the completed report as:

`dashboard/Healthcare_Operations.pbix`
