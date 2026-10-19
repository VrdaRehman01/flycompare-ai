
from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "ml" / "models" / "fare_ridge_model.joblib"


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}. Train it first."
        )

    saved = joblib.load(MODEL_PATH)
    model = saved["model"]

    examples = pd.DataFrame(
        [
            {
                "origin_city": "London",
                "destination_city": "New York",
                "departure_month": "2027-01",
            },
            {
                "origin_city": "Tokyo",
                "destination_city": "Singapore",
                "departure_month": "2027-01",
            },
            {
                "origin_city": "Dubai",
                "destination_city": "Paris",
                "departure_month": "2027-01",
            },
        ]
    )

    predictions = model.predict(examples)

    print("Historical monthly median fare estimates")
    print("Currency: EUR | Trip: one-way")
    print("-" * 60)

    for row, prediction in zip(examples.to_dict("records"), predictions):
        print(
            f"{row['origin_city']} -> {row['destination_city']}: "
            f"estimated €{max(0, prediction):.2f}"
        )

    print("\nModel evaluation:")
    print(f"Test month: {saved['test_month']}")
    print(f"Test MAE: €{saved['test_mae_eur']:.2f}")
    print(f"Baseline MAE: €{saved['baseline_mae_eur']:.2f}")

    print(
        "\nImportant: These are model estimates, not live ticket prices "
        "or guaranteed fares."
    )


if __name__ == "__main__":
    main()
