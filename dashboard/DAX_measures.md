# Power BI DAX Measures

After importing the PostgreSQL views, rename them in Power BI:

- `vw_fact_hospital_drg` → `Fact_Hospital_DRG`
- `vw_dim_hospital` → `Dim_Hospital`
- `vw_dim_drg` → `Dim_DRG`

Create these measures in `Fact_Hospital_DRG`.

## Volume measures

```DAX
Total Hospitals =
DISTINCTCOUNT(Fact_Hospital_DRG[provider_ccn])
```

```DAX
Total DRGs =
DISTINCTCOUNT(Fact_Hospital_DRG[drg_code])
```

```DAX
Total Discharges =
SUM(Fact_Hospital_DRG[total_discharges])
```

```DAX
Average Discharges per Hospital =
DIVIDE([Total Discharges], [Total Hospitals])
```

## Estimated totals

```DAX
Estimated Submitted Charges =
SUM(Fact_Hospital_DRG[estimated_submitted_charges])
```

```DAX
Estimated Total Payments =
SUM(Fact_Hospital_DRG[estimated_total_payments])
```

```DAX
Estimated Medicare Payments =
SUM(Fact_Hospital_DRG[estimated_medicare_payments])
```

```DAX
Estimated Payment Gap =
[Estimated Submitted Charges] - [Estimated Total Payments]
```

The estimated submitted-charge measure is not actual revenue.

## Discharge-weighted averages

```DAX
Weighted Avg Submitted Charge =
DIVIDE([Estimated Submitted Charges], [Total Discharges])
```

```DAX
Weighted Avg Total Payment =
DIVIDE([Estimated Total Payments], [Total Discharges])
```

```DAX
Weighted Avg Medicare Payment =
DIVIDE([Estimated Medicare Payments], [Total Discharges])
```

```DAX
Weighted Avg Payment Gap =
[Weighted Avg Submitted Charge] - [Weighted Avg Total Payment]
```

## Coverage and ratio measures

```DAX
Total Payment Coverage % =
DIVIDE([Estimated Total Payments], [Estimated Submitted Charges])
```

```DAX
Medicare Coverage % =
DIVIDE([Estimated Medicare Payments], [Estimated Submitted Charges])
```

```DAX
Aggregate Charge to Payment Ratio =
DIVIDE([Estimated Submitted Charges], [Estimated Total Payments])
```

## Ranking and benchmarking

```DAX
Hospital Discharge Rank =
RANKX(
    ALLSELECTED(Dim_Hospital[provider_ccn]),
    [Total Discharges],
    ,
    DESC,
    DENSE
)
```

```DAX
DRG Discharge Rank =
RANKX(
    ALLSELECTED(Dim_DRG[drg_code]),
    [Total Discharges],
    ,
    DESC,
    DENSE
)
```

```DAX
State Weighted Avg Submitted Charge =
CALCULATE(
    [Weighted Avg Submitted Charge],
    REMOVEFILTERS(Dim_Hospital[provider_ccn]),
    REMOVEFILTERS(Dim_Hospital[provider_name])
)
```

```DAX
Difference from State Weighted Charge =
[Weighted Avg Submitted Charge] - [State Weighted Avg Submitted Charge]
```

```DAX
Difference from State Weighted Charge % =
DIVIDE(
    [Difference from State Weighted Charge],
    [State Weighted Avg Submitted Charge]
)
```

## Suggested formatting

| Measure group | Power BI format |
|---|---|
| Counts and discharges | Whole number with thousands separator |
| Estimated totals | Currency, display units in millions or billions |
| Weighted averages and gaps | Currency with 0–2 decimal places |
| Coverage measures | Percentage with 1 decimal place |
| Charge-to-payment ratio | Decimal with 2 decimal places |
| Ranks | Whole number |

Coverage measures compare payments with submitted charges. They are not collection rates.

## Forecast-page measures

Create these after importing `Forecast_Model_Metrics`.

```DAX
Best Forecast RMSE =
MIN(Forecast_Model_Metrics[RMSE])
```

```DAX
Selected Forecast Model =
VAR BestModelRow =
    TOPN(
        1,
        ALL(Forecast_Model_Metrics),
        Forecast_Model_Metrics[RMSE],
        ASC
    )
RETURN
    CONCATENATEX(BestModelRow, Forecast_Model_Metrics[Model], "")
```

```DAX
Best Forecast MAE =
VAR BestModelRow =
    TOPN(
        1,
        ALL(Forecast_Model_Metrics),
        Forecast_Model_Metrics[RMSE],
        ASC
    )
RETURN
    MAXX(BestModelRow, Forecast_Model_Metrics[MAE])
```

```DAX
Best Forecast MAPE % =
VAR BestModelRow =
    TOPN(
        1,
        ALL(Forecast_Model_Metrics),
        Forecast_Model_Metrics[RMSE],
        ASC
    )
RETURN
    DIVIDE(
        MAXX(BestModelRow, Forecast_Model_Metrics[MAPE_Pct]),
        100
    )
```

Format MAE and RMSE as decimal numbers with three places and MAPE as a
percentage with one decimal place.
