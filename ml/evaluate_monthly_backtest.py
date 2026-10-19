
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"

df = pd.read_csv(DATA_PATH)

# Keep the same clean, route-month records used by the existing model.
df = df.dropna(subset=FEATURES + [TARGET]).copy()
df["departure_month"] = df["departure_month"].astype(str)

months = sorted(df["departure_month"].unique())

print(f"Dataset rows: {len(df):,}")
print(f"Departure months: {months}")
print("\nExpanding-window monthly backtest")
print("-" * 78)

results = []

for test_month in months[1:]:
    train = df[df["departure_month"] < test_month]
    test = df[df["departure_month"] == test_month]

    if train.empty or test.empty:
        continue

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                FEATURES,
            )
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("regression", Ridge(alpha=1.0)),
        ]
    )

    # Train against log fares, then convert predictions back to euros.
    model.fit(train[FEATURES], np.log1p(train[TARGET]))
    predictions = np.expm1(model.predict(test[FEATURES]))
    predictions = np.maximum(predictions, 0)

    # Baseline: predict the median fare from the training months.
    baseline_predictions = np.full(
        len(test), train[TARGET].median()
    )

    model_mae = mean_absolute_error(test[TARGET], predictions)
    model_rmse = np.sqrt(
        mean_squared_error(test[TARGET], predictions)
    )
    baseline_mae = mean_absolute_error(
        test[TARGET], baseline_predictions
    )
    baseline_rmse = np.sqrt(
        mean_squared_error(test[TARGET], baseline_predictions)
    )

    results.append(
        {
            "test_month": test_month,
            "train_rows": len(train),
            "test_rows": len(test),
            "model_MAE_EUR": model_mae,
            "baseline_MAE_EUR": baseline_mae,
            "model_RMSE_EUR": model_rmse,
            "baseline_RMSE_EUR": baseline_rmse,
            "MAE_improvement_pct": (
                (baseline_mae - model_mae) / baseline_mae * 100
                if baseline_mae else 0
            ),
        }
    )

    print(f"\nTest month: {test_month}")
    print(f"Training rows: {len(train):,} | Test rows: {len(test):,}")
    print(f"Log-Ridge MAE: €{model_mae:.2f}")
    print(f"Median baseline MAE: €{baseline_mae:.2f}")
    print(f"Log-Ridge RMSE: €{model_rmse:.2f}")
    print(f"Median baseline RMSE: €{baseline_rmse:.2f}")

results_df = pd.DataFrame(results)

if not results_df.empty:
    output_path = ROOT / "monthly_backtest_results.csv"
    results_df.to_csv(output_path, index=False)

    print("\n" + "=" * 78)
    print("SUMMARY")
    print(results_df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"\nResults saved to: {output_path}")
