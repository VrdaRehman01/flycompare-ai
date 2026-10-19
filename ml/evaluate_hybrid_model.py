
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
TEST_MONTH = "2027-01"

FEATURES = ["origin_city", "destination_city", "departure_month"]

df = pd.read_csv(DATA_PATH).dropna(
    subset=FEATURES + ["median_eur"]
).copy()

train = df[df["departure_month"] < TEST_MONTH].copy()
test = df[df["departure_month"] == TEST_MONTH].copy()

y_train = train["median_eur"].astype(float)
y_test = test["median_eur"].astype(float)

# Identify exact directional routes present in training.
train_routes = set(zip(train["origin_city"], train["destination_city"]))
test_routes = list(zip(test["origin_city"], test["destination_city"]))
seen_route = np.array([route in train_routes for route in test_routes])

# Model 1: Log-Ridge
ridge_preprocessor = ColumnTransformer([
    ("categorical", OneHotEncoder(handle_unknown="ignore"), FEATURES)
])

ridge = Pipeline([
    ("preprocessor", ridge_preprocessor),
    ("model", Ridge(alpha=1.0)),
])

ridge.fit(train[FEATURES], np.log1p(y_train))
ridge_predictions = np.maximum(
    0, np.expm1(ridge.predict(test[FEATURES]))
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

forest.fit(train[FEATURES], y_train)
forest_predictions = np.maximum(0, forest.predict(test[FEATURES]))

# Hybrid: use the model with the stronger observed result for each group.
hybrid_predictions = np.where(
    seen_route,
    forest_predictions,
    ridge_predictions,
)

# Baseline: median fare in training.
baseline = DummyRegressor(strategy="median")
baseline.fit(np.zeros((len(train), 1)), y_train)
baseline_predictions = baseline.predict(np.zeros((len(test), 1)))


def report(label, mask):
    actual = y_test.to_numpy()[mask]
    print(f"\n{label} (n={len(actual):,})")

    if len(actual) == 0:
        print("No rows in this group.")
        return

    candidates = {
        "Log-Ridge": ridge_predictions[mask],
        "Random Forest": forest_predictions[mask],
        "Hybrid": hybrid_predictions[mask],
        "Median baseline": baseline_predictions[mask],
    }

    for name, pred in candidates.items():
        mae = mean_absolute_error(actual, pred)
        rmse = np.sqrt(mean_squared_error(actual, pred))
        print(f"{name:16s} MAE €{mae:.2f} | RMSE €{rmse:.2f}")


print(f"Training rows: {len(train):,}")
print(f"Test rows: {len(test):,}")
print(f"Seen-route rows: {seen_route.sum():,}")
print(f"Unseen-route rows: {(~seen_route).sum():,}")

report("ALL ROUTES", np.ones(len(test), dtype=bool))
report("SEEN ROUTES", seen_route)
report("UNSEEN ROUTES", ~seen_route)

output = pd.DataFrame({
    "actual_eur": y_test.to_numpy(),
    "seen_route": seen_route,
    "log_ridge_eur": ridge_predictions,
    "random_forest_eur": forest_predictions,
    "hybrid_eur": hybrid_predictions,
    "baseline_eur": baseline_predictions,
})

output_path = ROOT / "hybrid_model_predictions.csv"
output.to_csv(output_path, index=False)
print(f"\nPredictions saved to: {output_path}")
