
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

FEATURES = ["origin_city", "destination_city", "departure_month"]

df = pd.read_csv(DATA_PATH)
df = df.dropna(subset=FEATURES + ["median_eur"]).copy()
df["median_eur"] = pd.to_numeric(df["median_eur"], errors="raise")

months = sorted(df["departure_month"].unique())
results = []

for test_month in months[1:]:
    train = df[df["departure_month"] < test_month].copy()
    test = df[df["departure_month"] == test_month].copy()

    if train.empty or test.empty:
        continue

    X_train = train[FEATURES]
    X_test = test[FEATURES]
    y_train = train["median_eur"]
    y_test = test["median_eur"]

    # Model 1: Log-Ridge
    ridge_preprocessor = ColumnTransformer([
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            FEATURES,
        )
    ])

    ridge = Pipeline([
        ("preprocessor", ridge_preprocessor),
        ("model", Ridge(alpha=1.0)),
    ])

    ridge.fit(X_train, np.log1p(y_train))
    ridge_predictions = np.maximum(
        0, np.expm1(ridge.predict(X_test))
    )

    # Model 2: Random Forest
    forest_preprocessor = ColumnTransformer([
        (
            "categorical",
            OrdinalEncoder(
                handle_unknown="use_encoded_value",
                unknown_value=-1,
            ),
            FEATURES,
        )
    ])

    forest = Pipeline([
        ("preprocessor", forest_preprocessor),
        (
            "model",
            RandomForestRegressor(
                n_estimators=150,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    forest.fit(X_train, y_train)
    forest_predictions = np.maximum(
        0, forest.predict(X_test)
    )

    # Model 3: Median baseline
    baseline = DummyRegressor(strategy="median")
    baseline.fit(np.zeros((len(train), 1)), y_train)
    baseline_predictions = baseline.predict(
        np.zeros((len(test), 1))
    )

    for name, predictions in [
        ("Log-Ridge", ridge_predictions),
        ("Random Forest", forest_predictions),
        ("Median Baseline", baseline_predictions),
    ]:
        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(
            mean_squared_error(y_test, predictions)
        )

        results.append({
            "test_month": test_month,
            "train_rows": len(train),
            "test_rows": len(test),
            "model": name,
            "MAE_EUR": mae,
            "RMSE_EUR": rmse,
        })

    print(f"\nTest month: {test_month}")
    print(f"Rows: {len(train):,} train / {len(test):,} test")

    for name, predictions in [
        ("Log-Ridge", ridge_predictions),
        ("Random Forest", forest_predictions),
        ("Median Baseline", baseline_predictions),
    ]:
        print(
            f"{name:16s} "
            f"MAE €{mean_absolute_error(y_test, predictions):.2f} | "
            f"RMSE €{np.sqrt(mean_squared_error(y_test, predictions)):.2f}"
        )

results_df = pd.DataFrame(results)

print("\n" + "=" * 80)
print("MONTHLY COMPARISON")
print(
    results_df.pivot(
        index="test_month",
        columns="model",
        values="MAE_EUR",
    ).round(2).to_string()
)

print("\nAVERAGE MAE ACROSS TEST MONTHS")
print(
    results_df.groupby("model")["MAE_EUR"]
    .mean()
    .sort_values()
    .round(2)
    .to_string()
)

output_path = ROOT / "ridge_forest_monthly_comparison.csv"
results_df.to_csv(output_path, index=False)
print(f"\nResults saved to: {output_path}")
