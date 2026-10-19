
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

FEATURES = ["origin_city", "destination_city", "departure_month"]

df = pd.read_csv(DATA_PATH)
df = df.dropna(
    subset=FEATURES + ["median_eur"]
).copy()

df["median_eur"] = pd.to_numeric(df["median_eur"], errors="raise")
months = sorted(df["departure_month"].unique())

results = []

for test_month in months[1:]:
    train = df[df["departure_month"] < test_month].copy()
    test = df[df["departure_month"] == test_month].copy()

    if train.empty or test.empty:
        continue

    preprocessor = ColumnTransformer(
        [
            (
                "categorical",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                ),
                FEATURES,
            )
        ]
    )

    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=150,
                    min_samples_leaf=5,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    model.fit(train[FEATURES], train["median_eur"])

    predictions = np.maximum(
        0,
        model.predict(test[FEATURES]),
    )

    baseline = DummyRegressor(strategy="median")
    baseline.fit(
        np.zeros((len(train), 1)),
        train["median_eur"],
    )
    baseline_predictions = baseline.predict(
        np.zeros((len(test), 1))
    )

    model_mae = mean_absolute_error(
        test["median_eur"], predictions
    )
    baseline_mae = mean_absolute_error(
        test["median_eur"], baseline_predictions
    )
    model_rmse = np.sqrt(
        mean_squared_error(test["median_eur"], predictions)
    )
    baseline_rmse = np.sqrt(
        mean_squared_error(
            test["median_eur"], baseline_predictions
        )
    )

    results.append(
        {
            "test_month": test_month,
            "train_rows": len(train),
            "test_rows": len(test),
            "random_forest_MAE_EUR": model_mae,
            "baseline_MAE_EUR": baseline_mae,
            "random_forest_RMSE_EUR": model_rmse,
            "baseline_RMSE_EUR": baseline_rmse,
            "MAE_improvement_pct": (
                (baseline_mae - model_mae) / baseline_mae * 100
                if baseline_mae
                else 0
            ),
        }
    )

    print(f"\nTest month: {test_month}")
    print(f"Training rows: {len(train):,} | Test rows: {len(test):,}")
    print(f"Random Forest MAE: €{model_mae:.2f}")
    print(f"Median baseline MAE: €{baseline_mae:.2f}")
    print(f"Random Forest RMSE: €{model_rmse:.2f}")
    print(f"Median baseline RMSE: €{baseline_rmse:.2f}")

results_df = pd.DataFrame(results)

print("\n" + "=" * 75)
print("SUMMARY")
print(results_df.round(2).to_string(index=False))

output_path = ROOT / "random_forest_backtest_results.csv"
results_df.to_csv(output_path, index=False)
print(f"\nResults saved to: {output_path}")
