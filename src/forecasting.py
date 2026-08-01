"""Forecast weekly COVID-NET hospitalization rates from official CDC data.

Source: CDC RESP-NET Rates and Clinical Data (dataset ID kvib-3txy).
The forecast is a complementary inpatient-demand indicator and is not joined
row-by-row to the CMS hospital-DRG financial dataset.
"""

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.holtwinters import ExponentialSmoothing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "resp_net_hospitalization_rates.csv"
PROCESSED_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "covid_net_weekly_hospitalization_rates.csv"
)
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "analysis_outputs"

TEST_WEEKS = 52
FORECAST_WEEKS = 12
SEASONAL_PERIODS = 52
RECENT_HISTORY_WEEKS = 156

REQUIRED_COLUMNS = {
    "surveillance_network",
    "season",
    "date_type",
    "date",
    "age_category",
    "race",
    "sex",
    "state",
    "data_type",
    "estimate_type",
    "rate_type",
    "estimate",
}


def load_resp_net_data(path: Path = RAW_FILE) -> pd.DataFrame:
    """Load the unchanged CDC RESP-NET CSV and validate its live schema."""
    if not path.is_file():
        raise FileNotFoundError(f"CDC RESP-NET file not found: {path}")
    data = pd.read_csv(path, dtype="string")
    missing = sorted(REQUIRED_COLUMNS.difference(data.columns))
    if missing:
        raise ValueError(f"CDC source is missing columns: {', '.join(missing)}")
    return data


def prepare_weekly_series(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Filter one continuous overall COVID-NET observed weekly-rate series."""
    mask = (
        raw_data["surveillance_network"].eq("COVID-NET")
        & raw_data["date_type"].eq("Week Ending Date")
        & raw_data["age_category"].eq("Overall")
        & raw_data["race"].eq("All")
        & raw_data["sex"].eq("All")
        & raw_data["state"].eq("Overall")
        & raw_data["data_type"].eq("Weekly Rate")
        & raw_data["estimate_type"].eq("Rate per 100,000")
        & raw_data["rate_type"].eq("Observed")
    )
    series_data = raw_data.loc[mask, ["date", "season", "estimate"]].copy()
    if series_data.empty:
        raise ValueError("The requested COVID-NET overall weekly series is empty.")

    series_data["date"] = pd.to_datetime(series_data["date"], errors="coerce")
    series_data["estimate"] = pd.to_numeric(
        series_data["estimate"], errors="coerce"
    )
    if series_data[["date", "estimate"]].isna().any().any():
        raise ValueError("Invalid dates or estimates found in the modeling series.")

    series_data = series_data.sort_values("date").reset_index(drop=True)
    if series_data["date"].duplicated().any():
        raise ValueError("Duplicate week-ending dates found in the modeling series.")

    expected_dates = pd.date_range(
        series_data["date"].min(), series_data["date"].max(), freq="W-SAT"
    )
    actual_dates = pd.DatetimeIndex(series_data["date"])
    missing_dates = expected_dates.difference(actual_dates)
    extra_dates = actual_dates.difference(expected_dates)
    if len(missing_dates) or len(extra_dates):
        raise ValueError(
            "Weekly series is not continuous: "
            f"{len(missing_dates)} missing and {len(extra_dates)} off-frequency dates."
        )

    return series_data.rename(
        columns={
            "date": "Week_Ending_Date",
            "season": "Surveillance_Season",
            "estimate": "Hospitalization_Rate_Per_100k",
        }
    )


def split_series(
    data: pd.DataFrame, test_weeks: int = TEST_WEEKS
) -> tuple[pd.Series, pd.Series]:
    """Create a chronological train/test split without leakage."""
    values = data.set_index("Week_Ending_Date")[
        "Hospitalization_Rate_Per_100k"
    ].astype(float)
    values = values.asfreq("W-SAT")
    if len(values) <= test_weeks + (2 * SEASONAL_PERIODS):
        raise ValueError("Not enough history for seasonal training and testing.")
    return values.iloc[:-test_weeks], values.iloc[-test_weeks:]


def naive_forecast(train: pd.Series, horizon: int) -> np.ndarray:
    """Repeat the most recent observation."""
    return np.repeat(float(train.iloc[-1]), horizon)


def moving_average_forecast(
    train: pd.Series, horizon: int, window: int = 4
) -> np.ndarray:
    """Repeat the mean of the most recent four observations."""
    return np.repeat(float(train.iloc[-window:].mean()), horizon)


def seasonal_naive_forecast(
    train: pd.Series, horizon: int, seasonal_periods: int = SEASONAL_PERIODS
) -> np.ndarray:
    """Repeat observations from the equivalent weeks one year earlier."""
    if len(train) < seasonal_periods:
        raise ValueError("Seasonal naive forecast requires at least one full season.")
    pattern = train.iloc[-seasonal_periods:].to_numpy(dtype=float)
    repeats = int(np.ceil(horizon / seasonal_periods))
    return np.tile(pattern, repeats)[:horizon]


def linear_trend_forecast(train: pd.Series, horizon: int) -> np.ndarray:
    """Extrapolate an ordinary least-squares linear time trend."""
    time = np.arange(len(train), dtype=float)
    slope, intercept = np.polyfit(time, train.to_numpy(dtype=float), 1)
    future_time = np.arange(len(train), len(train) + horizon, dtype=float)
    return np.maximum(0.0, intercept + slope * future_time)


def holt_winters_forecast(train: pd.Series, horizon: int) -> np.ndarray:
    """Fit additive Holt-Winters trend and annual weekly seasonality."""
    model = ExponentialSmoothing(
        train.to_numpy(dtype=float),
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=SEASONAL_PERIODS,
        initialization_method="estimated",
    ).fit(optimized=True, remove_bias=True)
    return np.maximum(0.0, np.asarray(model.forecast(horizon), dtype=float))


def recent_autoregression_forecast(
    train: pd.Series,
    horizon: int,
    history_weeks: int = RECENT_HISTORY_WEEKS,
) -> np.ndarray:
    """Forecast from recent history using short lags and an annual weekly lag."""
    if len(train) < history_weeks:
        raise ValueError(
            f"Recent autoregression requires at least {history_weeks} observations."
        )
    recent = train.iloc[-history_weeks:].to_numpy(dtype=float)
    model = AutoReg(
        recent,
        lags=[1, 2, 3, 4, SEASONAL_PERIODS],
        trend="ct",
        old_names=False,
    ).fit()
    predicted = model.predict(
        start=len(recent), end=len(recent) + horizon - 1, dynamic=False
    )
    return np.maximum(0.0, np.asarray(predicted, dtype=float))


def calculate_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    """Calculate MAE, RMSE, and zero-safe MAPE."""
    actual_values = actual.to_numpy(dtype=float)
    errors = actual_values - predicted
    nonzero = actual_values != 0
    return {
        "MAE": float(np.mean(np.abs(errors))),
        "RMSE": float(np.sqrt(np.mean(np.square(errors)))),
        "MAPE_Pct": float(
            np.mean(np.abs(errors[nonzero] / actual_values[nonzero])) * 100
        )
        if nonzero.any()
        else float("nan"),
    }


def evaluate_models(
    train: pd.Series, test: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    """Evaluate baseline and statistical models on the same test period."""
    model_functions: dict[str, Callable[[pd.Series, int], np.ndarray]] = {
        "Naive_Last_Value": naive_forecast,
        "Moving_Average_4_Week": moving_average_forecast,
        "Seasonal_Naive_52_Week": seasonal_naive_forecast,
        "Linear_Trend": linear_trend_forecast,
        "Holt_Winters_Additive": holt_winters_forecast,
        "AutoReg_Recent_156_Weeks": recent_autoregression_forecast,
    }
    predictions: dict[str, np.ndarray] = {}
    metric_rows: list[dict[str, object]] = []

    for model_name, forecast_function in model_functions.items():
        predicted = forecast_function(train, len(test))
        predictions[model_name] = predicted
        metric_rows.append(
            {"Model": model_name, **calculate_metrics(test, predicted)}
        )

    metrics = pd.DataFrame(metric_rows).sort_values("RMSE").reset_index(drop=True)
    test_predictions = pd.DataFrame(
        {
            "Week_Ending_Date": test.index,
            "Actual_Rate_Per_100k": test.to_numpy(dtype=float),
            **{
                f"Predicted_{name}": values
                for name, values in predictions.items()
            },
        }
    )
    return metrics, test_predictions, predictions


def forecast_with_selected_model(
    full_series: pd.Series,
    model_name: str,
    validation_actual: pd.Series,
    validation_prediction: np.ndarray,
    horizon: int = FORECAST_WEEKS,
) -> pd.DataFrame:
    """Refit the selected model and create an empirical 95% interval."""
    model_functions: dict[str, Callable[[pd.Series, int], np.ndarray]] = {
        "Naive_Last_Value": naive_forecast,
        "Moving_Average_4_Week": moving_average_forecast,
        "Seasonal_Naive_52_Week": seasonal_naive_forecast,
        "Linear_Trend": linear_trend_forecast,
        "Holt_Winters_Additive": holt_winters_forecast,
        "AutoReg_Recent_156_Weeks": recent_autoregression_forecast,
    }
    point_forecast = model_functions[model_name](full_series, horizon)
    residuals = validation_actual.to_numpy(dtype=float) - validation_prediction
    residual_std = float(np.std(residuals, ddof=1))
    margin = 1.96 * residual_std
    future_dates = pd.date_range(
        full_series.index.max() + pd.Timedelta(days=7),
        periods=horizon,
        freq="W-SAT",
    )
    return pd.DataFrame(
        {
            "Week_Ending_Date": future_dates,
            "Forecast_Rate_Per_100k": point_forecast,
            "Lower_95_Pct_Approx": np.maximum(0.0, point_forecast - margin),
            "Upper_95_Pct_Approx": point_forecast + margin,
            "Selected_Model": model_name,
        }
    )


def build_dashboard_data(
    prepared_data: pd.DataFrame, forecast: pd.DataFrame
) -> pd.DataFrame:
    """Combine history and forecast into a Power BI-friendly table."""
    history = prepared_data[
        ["Week_Ending_Date", "Hospitalization_Rate_Per_100k"]
    ].copy()
    history = history.rename(
        columns={"Hospitalization_Rate_Per_100k": "Actual_Rate_Per_100k"}
    )
    history["Forecast_Rate_Per_100k"] = np.nan
    history["Lower_95_Pct_Approx"] = np.nan
    history["Upper_95_Pct_Approx"] = np.nan
    history["Series_Type"] = "Historical"

    future = forecast.copy()
    future["Actual_Rate_Per_100k"] = np.nan
    future["Series_Type"] = "Forecast"
    future = future.drop(columns="Selected_Model")
    columns = [
        "Week_Ending_Date",
        "Actual_Rate_Per_100k",
        "Forecast_Rate_Per_100k",
        "Lower_95_Pct_Approx",
        "Upper_95_Pct_Approx",
        "Series_Type",
    ]
    return pd.concat([history[columns], future[columns]], ignore_index=True)


def save_outputs(
    prepared_data: pd.DataFrame,
    metrics: pd.DataFrame,
    test_predictions: pd.DataFrame,
    forecast: pd.DataFrame,
    dashboard_data: pd.DataFrame,
) -> None:
    """Save processed history and all reproducible forecast outputs."""
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prepared_data.to_csv(PROCESSED_FILE, index=False)
    metrics.to_csv(OUTPUT_DIR / "forecast_model_metrics.csv", index=False)
    test_predictions.to_csv(
        OUTPUT_DIR / "forecast_test_predictions.csv", index=False
    )
    forecast.to_csv(OUTPUT_DIR / "weekly_hospitalization_forecast.csv", index=False)
    dashboard_data.to_csv(
        OUTPUT_DIR / "forecast_dashboard_data.csv", index=False
    )


def main() -> None:
    """Run data preparation, model evaluation, selection, and forecasting."""
    raw_data = load_resp_net_data()
    prepared_data = prepare_weekly_series(raw_data)
    train, test = split_series(prepared_data)
    metrics, test_predictions, predictions = evaluate_models(train, test)
    selected_model = str(metrics.iloc[0]["Model"])

    full_series = prepared_data.set_index("Week_Ending_Date")[
        "Hospitalization_Rate_Per_100k"
    ].astype(float)
    forecast = forecast_with_selected_model(
        full_series,
        selected_model,
        test,
        predictions[selected_model],
    )
    dashboard_data = build_dashboard_data(prepared_data, forecast)
    save_outputs(
        prepared_data, metrics, test_predictions, forecast, dashboard_data
    )

    print("Forecasting pipeline validation summary")
    print("-" * 39)
    print(f"Raw source rows:       {len(raw_data):,}")
    print(f"Modeling weeks:        {len(prepared_data):,}")
    print(
        "Observed period:       "
        f"{prepared_data['Week_Ending_Date'].min().date()} to "
        f"{prepared_data['Week_Ending_Date'].max().date()}"
    )
    print(f"Training weeks:        {len(train):,}")
    print(f"Testing weeks:         {len(test):,}")
    print(f"Selected model:        {selected_model}")
    print(f"Forecast horizon:      {len(forecast):,} weeks")
    print("\nModel evaluation:")
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nOutputs saved to:      {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
