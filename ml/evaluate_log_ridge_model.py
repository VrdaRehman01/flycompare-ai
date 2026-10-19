
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"
TEST_MONTH = "2027-01"


def build_model():
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "cities_and_month",
                OneHotEncoder(handle_unknown="ignore"),
                FEATURES,
            )
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            ("regressor", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )


def main():
    print("Loading fare dataset...")
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)

    # Hold out the latest available month for testing.
    train = df[df["departure_month"] < TEST_MONTH].copy()
    test = df[df["departure_month"] == TEST_MONTH].copy()

    if train.empty or test.empty:
        raise ValueError(
            f"Cannot evaluate: training rows={len(train)}, "
            f"test rows={len(test)} for month {TEST_MONTH}."
        )

    model = build_model()
    model.fit(
        train[FEATURES],
        np.log1p(train[TARGET].astype(float)),
    )

    actual = test[TARGET].astype(float).to_numpy()
    predicted = np.maximum(
        0,
        np.expm1(model.predict(test[FEATURES])),
    )

    # Baseline: predict the median fare observed in the training data.
    baseline_value = float(train[TARGET].median())
    baseline = np.full(len(test), baseline_value)

    model_mae = mean_absolute_error(actual, predicted)
    model_rmse = np.sqrt(mean_squared_error(actual, predicted))
    baseline_mae = mean_absolute_error(actual, baseline)
    baseline_rmse = np.sqrt(mean_squared_error(actual, baseline))

    print("\n--- Holdout Evaluation ---")
    print(f"Training rows: {len(train):,}")
    print(f"Test rows: {len(test):,}")
    print(f"Test month: {TEST_MONTH}")
    print(f"Baseline fare: €{baseline_value:.2f}")
    print(f"Log-Ridge MAE: €{model_mae:.2f}")
    print(f"Log-Ridge RMSE: €{model_rmse:.2f}")
    print(f"Baseline MAE: €{baseline_mae:.2f}")
    print(f"Baseline RMSE: €{baseline_rmse:.2f}")

    if model_mae < baseline_mae:
        print("\nResult: Log-Ridge beats the baseline on MAE.")
    else:
        print("\nResult: Log-Ridge does not beat the baseline on MAE.")

    print(
        "\nNote: this evaluates one departure-month holdout. "
        "It does not establish performance for every future month."
    )


if __name__ == "__main__":
    main()
