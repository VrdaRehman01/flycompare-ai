
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"
TEST_MONTH = "2027-01"


def report(name, actual, predicted):
    mae = mean_absolute_error(actual, predicted)
    rmse = mean_squared_error(actual, predicted) ** 0.5
    print(f"{name}: MAE €{mae:.2f} | RMSE €{rmse:.2f}")
    return mae, rmse


def main():
    df = pd.read_csv(DATA_PATH)
    df["departure_month"] = df["departure_month"].astype(str)

    train = df[df["departure_month"] < TEST_MONTH].copy()
    test = df[df["departure_month"] == TEST_MONTH].copy()

    if train.empty or test.empty:
        raise ValueError("Training or test data is empty.")

    X_train = train[FEATURES]
    X_test = test[FEATURES]
    y_train = train[TARGET]
    y_test = test[TARGET]

    print(f"Training rows: {len(train):,}")
    print(f"Test rows: {len(test):,}")
    print(f"Test month: {TEST_MONTH}\n")

    # Model 1: existing successful log-target Ridge approach.
    ridge_preprocessor = ColumnTransformer(
        [("cities_and_month", OneHotEncoder(handle_unknown="ignore"), FEATURES)]
    )
    log_ridge = Pipeline([
        ("preprocessor", ridge_preprocessor),
        ("regressor", Ridge(alpha=10.0, solver="lsqr")),
    ])
    log_ridge.fit(X_train, np.log1p(y_train))
    ridge_predictions = np.maximum(
        0, np.expm1(log_ridge.predict(X_test))
    )
    ridge_mae, ridge_rmse = report(
        "Log-target Ridge", y_test, ridge_predictions
    )

    # Model 2: nonlinear gradient boosting with ordinal city encoding.
    # Unknown categories get a dedicated encoded value (-1).
    boosting_preprocessor = ColumnTransformer(
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

    boosting = Pipeline([
        ("preprocessor", boosting_preprocessor),
        (
            "regressor",
            HistGradientBoostingRegressor(
                max_iter=150,
                learning_rate=0.08,
                max_leaf_nodes=31,
                l2_regularization=1.0,
                random_state=42,
            ),
        ),
    ])

    boosting.fit(X_train, y_train)
    boosting_predictions = np.maximum(0, boosting.predict(X_test))
    boosting_mae, boosting_rmse = report(
        "HistGradientBoosting", y_test, boosting_predictions
    )

    print("\n--- Result ---")
    if boosting_mae < ridge_mae:
        print("Gradient boosting has lower overall MAE on this test set.")
    else:
        print("Log-target Ridge has lower overall MAE on this test set.")

    print("\n--- Fare-range MAE ---")
    bins = [0, 50, 100, 200, 300, 400, float("inf")]
    labels = ["€0–50", "€50–100", "€100–200", "€200–300", "€300–400", "Over €400"]
    ranges = pd.cut(y_test, bins=bins, labels=labels, include_lowest=True)

    comparison = pd.DataFrame({
        "fare_range": ranges,
        "actual": y_test.to_numpy(),
        "log_ridge": ridge_predictions,
        "boosting": boosting_predictions,
    })

    for label, group in comparison.groupby("fare_range", observed=False):
        if group.empty:
            continue

        ridge_error = (group["actual"] - group["log_ridge"]).abs().mean()
        boosting_error = (group["actual"] - group["boosting"]).abs().mean()

        print(
            f"{label}: log Ridge €{ridge_error:.2f} | "
            f"boosting €{boosting_error:.2f} | n={len(group):,}"
        )

    print(
        "\nThis experiment does not change your saved model. "
        "The test month remains January 2027."
    )


if __name__ == "__main__":
    main()
