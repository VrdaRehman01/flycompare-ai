
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
MODEL_PATH = ROOT / "ml" / "models" / "fare_ridge_model.joblib"


def main():
    df = pd.read_csv(DATA_PATH)
    df["departure_month"] = df["departure_month"].astype(str)

    saved = joblib.load(MODEL_PATH)
    model = saved["model"]
    test_month = saved["test_month"]

    train = df[df["departure_month"] < test_month].copy()
    test = df[df["departure_month"] == test_month].copy()

    if train.empty or test.empty:
        raise ValueError("Training or test data is empty.")

    # Identify whether each test route appeared in any training month.
    route_columns = ["origin_city", "destination_city"]
    training_routes = set(
        map(tuple, train[route_columns].drop_duplicates().to_numpy())
    )

    test_routes = list(map(tuple, test[route_columns].to_numpy()))
    test["route_seen_in_training"] = [
        route in training_routes for route in test_routes
    ]

    features = saved["features"]
    predictions = model.predict(test[features])
    test["prediction_eur"] = predictions
    test["absolute_error_eur"] = (
        test["prediction_eur"] - test["median_eur"]
    ).abs()

    baseline_prediction = train["median_eur"].median()
    test["baseline_error_eur"] = (
        test["median_eur"] - baseline_prediction
    ).abs()

    print(f"Test month: {test_month}")
    print(f"Training records: {len(train):,}")
    print(f"Test records: {len(test):,}")
    print(f"Baseline prediction: €{baseline_prediction:.2f}")

    for label, mask in [
        ("Routes seen in training", test["route_seen_in_training"]),
        ("Routes NOT seen in training", ~test["route_seen_in_training"]),
    ]:
        subset = test[mask]
        print(f"\n--- {label} ---")
        print(f"Records: {len(subset):,}")

        if subset.empty:
            print("No records in this group.")
            continue

        print(
            "Model MAE: "
            f"€{mean_absolute_error(subset['median_eur'], subset['prediction_eur']):.2f}"
        )
        print(
            "Baseline MAE: "
            f"€{subset['baseline_error_eur'].mean():.2f}"
        )

    print("\nThese are historical-fare estimates, not live ticket prices.")


if __name__ == "__main__":
    main()
