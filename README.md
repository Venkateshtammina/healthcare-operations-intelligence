# Healthcare Operations Intelligence

An end-to-end healthcare analytics project combining Medicare inpatient
operations, financial performance, and short-term hospitalization forecasting.

**Python | PostgreSQL | Power BI | DAX | Time-series forecasting**

[Download the Power BI report](dashboard/healthcare_operations_intelligence.pbix)
| [View the DAX measures](dashboard/DAX_measures.md)
| [Read the build guide](dashboard/Power_BI_build_guide.md)

## Overview

The project analyzes hospital and DRG-level inpatient activity to compare
volume, submitted charges, payments, coverage, and operational benchmarks. A
separate CDC COVID-NET series provides a complementary 12-week demand signal.

The CMS and CDC datasets remain independent; the forecast is not joined to
individual hospitals or DRGs.

## Key results

| Metric | Result |
|---|---:|
| Hospital-DRG records | 145,879 |
| Hospitals | 2,906 |
| DRGs | 540 |
| Inpatient discharges | 4,952,481 |
| Estimated total payments | $90.93B |
| Total-payment coverage | 19.87% |

Estimated financial totals are calculated from average source amounts and
discharges. They are analytical estimates, not audited hospital revenue.

## Dashboard

### Executive overview

National KPIs, state distribution, and the highest-volume hospitals and DRGs.

<p align="center">
  <img src="Dashboard%20images/executive-overview.png" alt="Executive Overview Power BI dashboard" width="100%">
</p>

<details>
  <summary><strong>Financial performance</strong></summary>
  <br>
  <p>Charges, payments, coverage ratios, hospital profiles, and high-volume ratio review.</p>
  <img src="Dashboard%20images/financial-performance.png" alt="Financial Performance Power BI dashboard" width="100%">
</details>

<details>
  <summary><strong>Operational performance</strong></summary>
  <br>
  <p>Rural and urban comparisons, state benchmarks, and hospital and DRG rankings.</p>
  <img src="Dashboard%20images/operational-performance.png" alt="Operational Performance Power BI dashboard" width="100%">
</details>

<details>
  <summary><strong>Forecasting</strong></summary>
  <br>
  <p>Recent actuals, 12-week forecast, uncertainty bounds, and model validation.</p>
  <img src="Dashboard%20images/forecasting.png" alt="Forecasting Power BI dashboard" width="100%">
</details>

## Data flow

```text
CMS hospital-DRG data -> Python cleaning -> PostgreSQL views -> Power BI
CDC RESP-NET data     -> Python forecasting -----------------> Power BI
```

The Power BI operational model uses a simple star schema:

```text
Dim Hospital (1) -> (*) Fact Hospital DRG (*) <- (1) Dim DRG
```

## Forecasting

Six models were evaluated on a chronological 52-week holdout. The selected
`AutoReg Recent 156 Weeks` model achieved:

| MAE | RMSE | MAPE | Horizon |
|---:|---:|---:|---:|
| 0.276 | 0.350 | 38.8% | 12 weeks |

Because hospitalization rates are close to zero, the forecast is intended for
directional planning rather than exact capacity commitments.

## Run locally

Place the official source files in `data/raw`, then run:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python src\data_cleaning.py
python src\eda_analysis.py
python src\forecasting.py
```

Build the PostgreSQL layer in this order:

```text
sql/schema.sql
sql/data_import.sql
sql/power_bi_views.sql
```

Expected validation: 145,879 fact rows, 2,906 hospitals, 540 DRGs, and
4,952,481 discharges.

## Repository contents

- `src/` - cleaning, exploratory analysis, and forecasting pipelines
- `sql/` - schema, import, analytical queries, and Power BI views
- `notebooks/` - data understanding, EDA, and forecasting notebooks
- `dashboard/` - PBIX report, DAX reference, and build guide
- `Dashboard images/` - report-page previews used above

Raw and generated datasets are excluded from version control.

## Data sources

- [CMS Medicare Inpatient Hospitals - by Provider and Service](https://data.cms.gov/provider-summary-by-type-of-service/medicare-inpatient-hospitals/medicare-inpatient-hospitals-by-provider-and-service)
- [CDC RESP-NET Rates and Clinical Data](https://data.cdc.gov/Public-Health-Surveillance/RESP-NET-Rates-and-Clinical-Data/kvib-3txy)

## Notes

- The CMS data represents Original Medicare fee-for-service inpatient activity,
  not each hospital's complete patient population.
- Estimated totals support comparison and should not be treated as audited
  financial statements.
- RESP-NET is a public-health surveillance signal, not a hospital-specific
  census forecast.
