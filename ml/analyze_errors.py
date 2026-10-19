
from pathlib import Path

import joblib
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
MODEL_PATH = ROOT / "ml" / "models" / "fare_ridge_model.joblib"


def main():
    df = pd.read_csv(DATA_PATH)
    df["departure_month"] = df["departure_month"].astype(str)

    saved = joblib.load(MODEL_PATH)
    test = df[df["departure_month"] == saved["test_month"]].copy()

    if test.empty:
        raise ValueError("No test records found for the saved test month.")

    model = saved["model"]
    features = saved["features"]

    test["predicted_eur"] = model.predict(test[features])
    test["actual_eur"] = test["median_eur"]
    test["absolute_error_eur"] = (
        test["predicted_eur"] - test["actual_eur"]
    ).abs()

    print("--- Error Summary ---")
    print(test["absolute_error_eur"].describe().round(2).to_string())

    print("\n--- Error by Actual Fare Range ---")
    bins = [0, 50, 100, 200, 300, 400, float("inf")]
    labels = [
        "€0–50",
        "€50–100",
        "€100–200",
        "€200–300",
        "€300–400",
        "Over €400",
    ]

    test["fare_range"] = pd.cut(
        test["actual_eur"],
        bins=bins,
        labels=labels,
        include_lowest=True,
    )

    grouped = test.groupby("fare_range", observed=False).agg(
        records=("actual_eur", "size"),
        actual_mean_eur=("actual_eur", "mean"),
        predicted_mean_eur=("predicted_eur", "mean"),
        mae_eur=("absolute_error_eur", "mean"),
    )

    print(grouped.round(2).to_string())

    print("\n--- Largest Prediction Errors ---")
    columns = [
        "origin_city",
        "destination_city",
        "actual_eur",
        "predicted_eur",
        "absolute_error_eur",
    ]

    print(
        test.nlargest(10, "absolute_error_eur")[columns]
        .round(2)
        .to_string(index=False)
    )

    print("\n--- Fare Ceiling Check ---")
    for column in ["median_eur", "p10_eur", "min_eur"]:
        count = int((df[column] == 400).sum())
        print(f"{column} equal to €400: {count:,} records")

    print(
        "\nThe €400 maximum is a pattern to investigate, "
        "not proof of a data cap."
    )


if __name__ == "__main__":
    main()
