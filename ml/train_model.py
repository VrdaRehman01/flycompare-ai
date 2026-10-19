
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "fare_ridge_model.joblib"

FEATURES = ["origin_city", "destination_city", "departure_month"]
TARGET = "median_eur"
TEST_MONTH = "2027-01"


def evaluate_model(name, model, X_train, y_train, X_test, y_test):
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5

    print(f"\n{name}")
    print(f"  MAE:  €{mae:.2f}")
    print(f"  RMSE: €{rmse:.2f}")

    return model, mae, rmse


def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)

    # Keep the target and features valid for this experiment.
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
    df["departure_month"] = df["departure_month"].astype(str)

    # Use a chronological holdout: the latest available month is the test set.
    train_df = df[df["departure_month"] < TEST_MONTH].copy()
    test_df = df[df["departure_month"] == TEST_MONTH].copy()

    if train_df.empty or test_df.empty:
        raise ValueError(
            f"Could not create train/test split for test month {TEST_MONTH}."
        )

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET]
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET]

    print(f"Training rows: {len(train_df):,}")
    print(f"Test rows: {len(test_df):,}")
    print(f"Training months: {sorted(train_df['departure_month'].unique())}")
    print(f"Test month: {TEST_MONTH}")
    print(f"Test routes: {len(test_df[['origin_city', 'destination_city']].drop_duplicates()):,}")

    # Baseline: always predict the median fare from the training data.
    baseline = DummyRegressor(strategy="median")
    _, baseline_mae, baseline_rmse = evaluate_model(
        "Baseline (training median)",
        baseline,
        X_train,
        y_train,
        X_test,
        y_test,
    )

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "cities_and_month",
                OneHotEncoder(handle_unknown="ignore"),
                FEATURES,
            )
        ]
    )

    ridge_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            ("regressor", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )

    trained_model, model_mae, model_rmse = evaluate_model(
        "Ridge Regression",
        ridge_pipeline,
        X_train,
        y_train,
        X_test,
        y_test,
    )

    print("\n--- Comparison ---")
    print(f"Baseline MAE: €{baseline_mae:.2f}")
    print(f"Model MAE:    €{model_mae:.2f}")

    if model_mae < baseline_mae:
        print("Result: Ridge improved on the baseline MAE.")
    else:
        print("Result: Ridge did not beat the baseline MAE.")

    # Save the model and metadata needed to interpret its predictions.
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": trained_model,
            "features": FEATURES,
            "target": TARGET,
            "currency": "EUR",
            "target_description": "Historical monthly median one-way fare",
            "training_months": sorted(train_df["departure_month"].unique()),
            "test_month": TEST_MONTH,
            "test_mae_eur": model_mae,
            "test_rmse_eur": model_rmse,
            "baseline_mae_eur": baseline_mae,
            "baseline_rmse_eur": baseline_rmse,
        },
        MODEL_PATH,
    )

    print(f"\nSaved model to: {MODEL_PATH}")
    print("Note: Predictions are estimates of historical monthly median fares,")
    print("not live prices, bookable offers, or guaranteed future fares.")


if __name__ == "__main__":
    main()
