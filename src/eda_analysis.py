"""Reusable exploratory-analysis tables for CMS inpatient hospital data."""

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "healthcare_operations_clean.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "analysis_outputs"

IDENTIFIER_DTYPES = {
    "Rndrng_Prvdr_CCN": "string",
    "Rndrng_Prvdr_State_FIPS": "string",
    "Rndrng_Prvdr_Zip5": "string",
    "DRG_Cd": "string",
}

VALUE_COLUMNS = [
    "Avg_Submtd_Cvrd_Chrg",
    "Avg_Tot_Pymt_Amt",
    "Avg_Mdcr_Pymt_Amt",
    "Payment_Gap",
    "Medicare_Payment_Gap",
    "Total_Payment_Coverage_Pct",
    "Medicare_Coverage_Pct",
    "Charge_to_Total_Payment_Ratio",
]

ESTIMATED_TOTAL_COLUMNS = [
    "Estimated_Submitted_Charges",
    "Estimated_Total_Payments",
    "Estimated_Medicare_Payments",
]


def load_clean_data(path: Path = INPUT_FILE) -> pd.DataFrame:
    """Load the validated analytical dataset."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Processed data not found: {path}. Run src/data_cleaning.py first."
        )
    return pd.read_csv(path, dtype=IDENTIFIER_DTYPES)


def weighted_average(
    values: pd.Series, weights: pd.Series
) -> float:
    """Return a weighted average, ignoring rows invalid for either input."""
    valid = values.notna() & weights.notna() & weights.gt(0)
    if not valid.any():
        return float("nan")
    return float(np.average(values.loc[valid], weights=weights.loc[valid]))


def add_rural_urban_group(df: pd.DataFrame) -> pd.DataFrame:
    """Map RUCA 1-3 to Urban, 4-10 to Rural, and other codes to Unknown."""
    result = df.copy()
    ruca = pd.to_numeric(result["Rndrng_Prvdr_RUCA"], errors="coerce")
    result["Rural_Urban_Group"] = np.select(
        [ruca.between(1, 3.99), ruca.between(4, 10.99)],
        ["Urban", "Rural"],
        default="Unknown",
    )
    return result


def calculate_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate portfolio-level volume and discharge-weighted financial KPIs."""
    discharges = df["Tot_Dschrgs"]
    kpis = {
        "Number_of_Hospitals": df["Rndrng_Prvdr_CCN"].nunique(),
        "Number_of_DRGs": df["DRG_Cd"].nunique(),
        "Number_of_States_and_Territories": df["Rndrng_Prvdr_State_Abrvtn"].nunique(),
        "Total_Discharges": discharges.sum(),
        "Weighted_Avg_Submitted_Charge": weighted_average(
            df["Avg_Submtd_Cvrd_Chrg"], discharges
        ),
        "Weighted_Avg_Total_Payment": weighted_average(
            df["Avg_Tot_Pymt_Amt"], discharges
        ),
        "Weighted_Avg_Medicare_Payment": weighted_average(
            df["Avg_Mdcr_Pymt_Amt"], discharges
        ),
        "Total_Estimated_Submitted_Charges": df["Estimated_Submitted_Charges"].sum(),
        "Total_Estimated_Payments": df["Estimated_Total_Payments"].sum(),
        "Total_Estimated_Medicare_Payments": df[
            "Estimated_Medicare_Payments"
        ].sum(),
    }
    return pd.DataFrame(
        {"KPI": list(kpis), "Value": list(kpis.values())}
    )


def grouped_summary(df: pd.DataFrame, group_columns: Iterable[str]) -> pd.DataFrame:
    """Build volume, total, and discharge-weighted metrics by a grouping."""
    groups = list(group_columns)
    working = df[
        groups + ["Tot_Dschrgs"] + VALUE_COLUMNS + ESTIMATED_TOTAL_COLUMNS
    ].copy()
    weighted_columns: list[str] = []
    for column in VALUE_COLUMNS:
        weighted_column = f"__weighted_{column}"
        working[weighted_column] = working[column] * working["Tot_Dschrgs"]
        weighted_columns.append(weighted_column)

    aggregations: dict[str, str] = {
        "Tot_Dschrgs": "sum",
        **{column: "sum" for column in ESTIMATED_TOTAL_COLUMNS},
        **{column: "sum" for column in weighted_columns},
    }
    summary = (
        working.groupby(groups, dropna=False, observed=True)
        .agg(**{
            "Total_Discharges": ("Tot_Dschrgs", "sum"),
            "Service_Record_Count": ("Tot_Dschrgs", "size"),
            **{
                f"Total_{column}": (column, "sum")
                for column in ESTIMATED_TOTAL_COLUMNS
            },
            **{
                weighted_column: (weighted_column, "sum")
                for weighted_column in weighted_columns
            },
        })
        .reset_index()
    )
    for column, weighted_column in zip(VALUE_COLUMNS, weighted_columns):
        summary[f"Weighted_{column}"] = (
            summary[weighted_column] / summary["Total_Discharges"]
        )
    return summary.drop(columns=weighted_columns)


def create_analysis_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Create the reusable tables required by the core EDA questions."""
    analysis_df = add_rural_urban_group(df)

    hospitals = grouped_summary(
        analysis_df,
        ["Rndrng_Prvdr_CCN", "Rndrng_Prvdr_Org_Name", "Rndrng_Prvdr_State_Abrvtn"],
    ).sort_values("Total_Discharges", ascending=False)

    drgs = grouped_summary(analysis_df, ["DRG_Cd", "DRG_Desc"]).sort_values(
        "Total_Discharges", ascending=False
    )

    states = grouped_summary(
        analysis_df, ["Rndrng_Prvdr_State_Abrvtn"]
    ).sort_values("Total_Discharges", ascending=False)

    rural_urban = grouped_summary(
        analysis_df, ["Rural_Urban_Group"]
    ).sort_values("Total_Discharges", ascending=False)

    hospital_drg = grouped_summary(
        analysis_df,
        [
            "Rndrng_Prvdr_CCN",
            "Rndrng_Prvdr_Org_Name",
            "Rndrng_Prvdr_State_Abrvtn",
            "DRG_Cd",
            "DRG_Desc",
        ],
    ).sort_values("Total_Discharges", ascending=False)

    expensive_high_volume_drgs = drgs.loc[
        drgs["Total_Discharges"].ge(1_000)
    ].sort_values("Weighted_Avg_Submtd_Cvrd_Chrg", ascending=False)

    high_volume_cutoff = hospital_drg["Total_Discharges"].quantile(0.90)
    high_cost_cutoff = hospital_drg["Weighted_Avg_Submtd_Cvrd_Chrg"].quantile(0.90)
    high_volume_high_cost = hospital_drg.loc[
        hospital_drg["Total_Discharges"].ge(high_volume_cutoff)
        & hospital_drg["Weighted_Avg_Submtd_Cvrd_Chrg"].ge(high_cost_cutoff)
    ].sort_values(
        ["Total_Discharges", "Weighted_Avg_Submtd_Cvrd_Chrg"],
        ascending=False,
    )

    ratio_q1 = analysis_df["Charge_to_Total_Payment_Ratio"].quantile(0.25)
    ratio_q3 = analysis_df["Charge_to_Total_Payment_Ratio"].quantile(0.75)
    ratio_upper_fence = ratio_q3 + 1.5 * (ratio_q3 - ratio_q1)
    ratio_outliers = analysis_df.loc[
        analysis_df["Charge_to_Total_Payment_Ratio"].gt(ratio_upper_fence)
    ].sort_values("Charge_to_Total_Payment_Ratio", ascending=False)

    coverage_distribution = analysis_df[
        ["Total_Payment_Coverage_Pct", "Medicare_Coverage_Pct"]
    ].describe(percentiles=[0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]).T.reset_index()
    coverage_distribution = coverage_distribution.rename(columns={"index": "Metric"})

    return {
        "portfolio_kpis": calculate_kpis(analysis_df),
        "hospital_summary": hospitals,
        "drg_summary": drgs,
        "state_summary": states,
        "rural_urban_summary": rural_urban,
        "hospital_drg_summary": hospital_drg,
        "expensive_high_volume_drgs": expensive_high_volume_drgs,
        "high_volume_high_cost_combinations": high_volume_high_cost,
        "charge_to_payment_ratio_outliers": ratio_outliers,
        "coverage_percentage_distribution": coverage_distribution,
    }


def save_analysis_tables(
    tables: dict[str, pd.DataFrame], output_dir: Path = OUTPUT_DIR
) -> None:
    """Save each analysis table as a Power BI- and SQL-friendly CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(output_dir / f"{name}.csv", index=False)


def main() -> None:
    """Generate all reusable EDA output tables."""
    data = load_clean_data()
    tables = create_analysis_tables(data)
    save_analysis_tables(tables)

    print("EDA analysis tables created")
    print("-" * 30)
    print(f"Source rows:     {len(data):,}")
    print(f"Tables created:  {len(tables):,}")
    print(f"Output folder:   {OUTPUT_DIR}")
    for name, table in tables.items():
        print(f"  {name}.csv: {len(table):,} rows")


if __name__ == "__main__":
    main()
