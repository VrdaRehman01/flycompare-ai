
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
CURRENT_MODEL_PATH = ROOT / "ml" / "models" / "fare_ridge_model.joblib"

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

    X_train, X_test = train[FEATURES], test[FEATURES]
    y_train, y_test = train[TARGET], test[TARGET]

    # Existing model: compare using its saved artifact.
    current = joblib.load(CURRENT_MODEL_PATH)["model"]
    current_predictions = current.predict(X_test)

    # Log-target model: train on logarithmic fares.
    preprocessing = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), FEATURES)
        ]
    )

    log_model = Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            ("regressor", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )

    log_model.fit(X_train, np.log1p(y_train))
    log_predictions = np.expm1(log_model.predict(X_test))
    log_predictions = np.maximum(log_predictions, 0)

    baseline = DummyRegressor(strategy="median")
    baseline.fit(X_train, y_train)
    baseline_predictions = baseline.predict(X_test)

    print(f"Test month: {TEST_MONTH}")
    print(f"Training rows: {len(train):,} | Test rows: {len(test):,}\n")

    report("Baseline", y_test, baseline_predictions)
    report("Current Ridge", y_test, current_predictions)
    report("Log-target Ridge", y_test, log_predictions)

    print("\n--- MAE by Actual Fare Range ---")
    bins = [0, 50, 100, 200, 300, 400, float("inf")]
    labels = ["€0–50", "€50–100", "€100–200", "€200–300", "€300–400", "Over €400"]
    ranges = pd.cut(y_test, bins=bins, labels=labels, include_lowest=True)

    results = pd.DataFrame({
        "fare_range": ranges,
        "actual": y_test.to_numpy(),
        "current_prediction": current_predictions,
        "log_prediction": log_predictions,
    })

    for label, group in results.groupby("fare_range", observed=False):
        if group.empty:
            continue
        current_mae = (group["actual"] - group["current_prediction"]).abs().mean()
        log_mae = (group["actual"] - group["log_prediction"]).abs().mean()
        print(
            f"{label}: current MAE €{current_mae:.2f} | "
            f"log-target MAE €{log_mae:.2f} | records {len(group):,}"
        )

    print("\nThis is an experiment only; the saved production model was not changed.")


if __name__ == "__main__":
    main()
