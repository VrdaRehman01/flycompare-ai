
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "ml" / "models" / "fare_log_ridge_model.joblib"

FEATURES = ["origin_city", "destination_city", "departure_month"]


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_PATH}. "
            "Run ml/train_safe_log_ridge_model.py first."
        )

    saved = joblib.load(MODEL_PATH)

    if "model" not in saved:
        raise ValueError("Saved model artifact does not contain a model.")

    if saved.get("target_transform") != "log1p":
        raise ValueError("Unexpected model target transformation.")

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
        ],
        columns=FEATURES,
    )

    # The model predicts log1p(fare), so reverse the transformation.
    log_predictions = np.asarray(model.predict(examples), dtype=float)

    if not np.isfinite(log_predictions).all():
        raise ValueError("Model returned invalid prediction values.")

    predictions = np.maximum(0, np.expm1(log_predictions))

    print("Historical monthly median fare estimates")
    print("Currency: EUR | Trip: one-way")
    print("-" * 60)

    for row, prediction in zip(
        examples.to_dict("records"), predictions
    ):
        print(
            f"{row['origin_city']} -> {row['destination_city']}: "
            f"estimated EUR {prediction:.2f}"
        )

    evaluation = saved.get("evaluation", {})

    print("\nModel information:")
    print(f"Model: {saved.get('model_name', 'Unknown')}")
    print(f"Training rows: {saved.get('training_rows', 'Unknown'):,}")
    print(f"Training months: {', '.join(saved.get('training_months', []))}")

    if evaluation:
        print("\nRecorded holdout evaluation:")
        print(f"Test month: {evaluation.get('test_month', 'Unknown')}")
        print(f"Test MAE: EUR {evaluation.get('mae_eur', float('nan')):.2f}")
        print(f"Baseline MAE: EUR {evaluation.get('baseline_mae_eur', float('nan')):.2f}")
        print(f"Test RMSE: EUR {evaluation.get('rmse_eur', float('nan')):.2f}")
        print(
            "Note: these metrics evaluate the candidate model before "
            "final training on all available data."
        )

    print(
        "\nImportant: These are historical model estimates, not live "
        "ticket prices or guaranteed fares."
    )


if __name__ == "__main__":
    main()
