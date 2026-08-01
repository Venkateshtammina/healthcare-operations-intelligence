"""Clean CMS inpatient hospital data and create approved analytical features."""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "medicare_inpatient_hospitals.CSV"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "healthcare_operations_clean.csv"

REQUIRED_COLUMNS = {
    "Rndrng_Prvdr_CCN",
    "Rndrng_Prvdr_Org_Name",
    "Rndrng_Prvdr_St",
    "Rndrng_Prvdr_City",
    "Rndrng_Prvdr_State_FIPS",
    "Rndrng_Prvdr_Zip5",
    "Rndrng_Prvdr_State_Abrvtn",
    "Rndrng_Prvdr_RUCA",
    "Rndrng_Prvdr_RUCA_Desc",
    "DRG_Cd",
    "DRG_Desc",
    "Tot_Dschrgs",
    "Avg_Submtd_Cvrd_Chrg",
    "Avg_Tot_Pymt_Amt",
    "Avg_Mdcr_Pymt_Amt",
}

NUMERIC_COLUMNS = [
    "Tot_Dschrgs",
    "Avg_Submtd_Cvrd_Chrg",
    "Avg_Tot_Pymt_Amt",
    "Avg_Mdcr_Pymt_Amt",
]

# Read identifiers as text so leading zeroes are preserved.
IDENTIFIER_DTYPES = {
    "Rndrng_Prvdr_CCN": "string",
    "Rndrng_Prvdr_State_FIPS": "string",
    "Rndrng_Prvdr_Zip5": "string",
    "DRG_Cd": "string",
}


def load_data(path: Path) -> pd.DataFrame:
    """Load the raw CSV while preserving identifier formatting."""
    if not path.is_file():
        raise FileNotFoundError(f"Raw data file not found: {path}")

    try:
        return pd.read_csv(path, dtype=IDENTIFIER_DTYPES)
    except (OSError, pd.errors.ParserError) as exc:
        raise RuntimeError(f"Could not read raw data file: {path}") from exc


def validate_required_columns(df: pd.DataFrame) -> None:
    """Raise an error when one or more required source columns are absent."""
    missing_columns = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")


def clean_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with leading and trailing whitespace removed from text."""
    cleaned = df.copy()
    text_columns = cleaned.select_dtypes(include=["object", "string"]).columns
    for column in text_columns:
        cleaned[column] = cleaned[column].str.strip()
    return cleaned


def validate_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert analytical fields to numeric and reject invalid values."""
    validated = df.copy()

    for column in NUMERIC_COLUMNS:
        original_non_null = validated[column].notna()
        validated[column] = pd.to_numeric(validated[column], errors="coerce")
        invalid_count = int((original_non_null & validated[column].isna()).sum())
        if invalid_count:
            raise ValueError(f"{column} contains {invalid_count:,} non-numeric value(s).")

    missing_counts = validated[NUMERIC_COLUMNS].isna().sum()
    if missing_counts.any():
        details = ", ".join(
            f"{column}: {count:,}"
            for column, count in missing_counts.items()
            if count
        )
        raise ValueError(f"Missing numeric values found ({details}).")

    negative_counts = validated[NUMERIC_COLUMNS].lt(0).sum()
    if negative_counts.any():
        details = ", ".join(
            f"{column}: {count:,}"
            for column, count in negative_counts.items()
            if count
        )
        raise ValueError(f"Negative numeric values found ({details}).")

    if not np.isfinite(validated[NUMERIC_COLUMNS].to_numpy()).all():
        raise ValueError("Infinite values found in numeric columns.")

    return validated


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create approved payment, coverage, and estimated-total metrics."""
    featured = df.copy()
    submitted_charge = featured["Avg_Submtd_Cvrd_Chrg"]
    total_payment = featured["Avg_Tot_Pymt_Amt"]
    medicare_payment = featured["Avg_Mdcr_Pymt_Amt"]
    discharges = featured["Tot_Dschrgs"]

    featured["Payment_Gap"] = submitted_charge - total_payment
    featured["Medicare_Payment_Gap"] = submitted_charge - medicare_payment

    # Undefined ratios remain NaN if a future input contains a zero denominator.
    featured["Total_Payment_Coverage_Pct"] = (
        total_payment.div(submitted_charge.where(submitted_charge.ne(0))) * 100
    )
    featured["Medicare_Coverage_Pct"] = (
        medicare_payment.div(submitted_charge.where(submitted_charge.ne(0))) * 100
    )
    featured["Estimated_Submitted_Charges"] = submitted_charge * discharges
    featured["Estimated_Total_Payments"] = total_payment * discharges
    featured["Estimated_Medicare_Payments"] = medicare_payment * discharges
    featured["Charge_to_Total_Payment_Ratio"] = submitted_charge.div(
        total_payment.where(total_payment.ne(0))
    )

    return featured


def save_data(df: pd.DataFrame, path: Path) -> None:
    """Create the output directory if needed and save the cleaned CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_csv(path, index=False)
    except OSError as exc:
        raise RuntimeError(f"Could not save cleaned data to: {path}") from exc


def print_validation_summary(
    df: pd.DataFrame, input_rows: int, output_path: Path
) -> None:
    """Print a concise, reproducible data-quality summary."""
    zero_submitted = int(df["Avg_Submtd_Cvrd_Chrg"].eq(0).sum())
    zero_total_payment = int(df["Avg_Tot_Pymt_Amt"].eq(0).sum())

    print("\nData cleaning validation summary")
    print("-" * 36)
    print(f"Input rows:                    {input_rows:,}")
    print(f"Output rows:                   {len(df):,}")
    print(f"Rows removed:                  {input_rows - len(df):,}")
    print(f"Duplicate rows:                {df.duplicated().sum():,}")
    print(f"Missing cells:                 {df.isna().sum().sum():,}")
    print(f"Zero submitted-charge values:  {zero_submitted:,}")
    print(f"Zero total-payment values:     {zero_total_payment:,}")
    print(f"Columns after processing:      {df.shape[1]:,}")
    print(f"Output file:                   {output_path}")


def main() -> None:
    """Run the complete cleaning and feature-engineering pipeline."""
    raw_data = load_data(RAW_FILE)
    input_rows = len(raw_data)

    validate_required_columns(raw_data)
    cleaned_data = clean_text_columns(raw_data)
    cleaned_data = validate_numeric_columns(cleaned_data)
    cleaned_data = create_features(cleaned_data)

    if len(cleaned_data) != input_rows:
        raise RuntimeError("Unexpected row-count change during processing.")

    save_data(cleaned_data, OUTPUT_FILE)
    print_validation_summary(cleaned_data, input_rows, OUTPUT_FILE)


if __name__ == "__main__":
    main()
