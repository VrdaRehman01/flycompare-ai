
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
TEST_MONTH = "2027-01"

df = pd.read_csv(DATA_PATH)

features = [
    "origin_city",
    "destination_city",
    "departure_month",
]

train = df[df["departure_month"] < TEST_MONTH].copy()
test = df[df["departure_month"] == TEST_MONTH].copy()

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            features,
        )
    ]
)

model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("regressor", Ridge(alpha=1.0)),
    ]
)

model.fit(train[features], np.log1p(train["median_eur"]))

test["predicted_eur"] = np.maximum(
    0,
    np.expm1(model.predict(test[features])),
)

test["error_eur"] = test["predicted_eur"] - test["median_eur"]
test["absolute_error_eur"] = test["error_eur"].abs()

bins = [0, 50, 100, 200, 300, 400.01]
labels = ["€0–50", "€50–100", "€100–200", "€200–300", "€300–400"]

test["fare_band"] = pd.cut(
    test["median_eur"],
    bins=bins,
    labels=labels,
    right=False,
    include_lowest=True,
)

summary = (
    test.groupby("fare_band", observed=False)
    .agg(
        rows=("median_eur", "size"),
        actual_mean_eur=("median_eur", "mean"),
        predicted_mean_eur=("predicted_eur", "mean"),
        mae_eur=("absolute_error_eur", "mean"),
        bias_eur=("error_eur", "mean"),
    )
    .reset_index()
)

summary["rmse_eur"] = [
    np.sqrt(
        mean_squared_error(
            test.loc[test["fare_band"] == band, "median_eur"],
            test.loc[test["fare_band"] == band, "predicted_eur"],
        )
    )
    if (test["fare_band"] == band).any()
    else np.nan
    for band in summary["fare_band"]
]

print(f"Training rows: {len(train):,}")
print(f"Test rows: {len(test):,}")
print("\nLog-Ridge error analysis by actual fare band")
print(summary.round(2).to_string(index=False))

output_path = ROOT / "log_model_error_analysis.csv"
summary.to_csv(output_path, index=False)
print(f"\nResults saved to: {output_path}")
