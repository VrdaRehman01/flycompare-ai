
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
TEST_MONTH = "2027-01"

FEATURES = ["origin_city", "destination_city", "departure_month"]

df = pd.read_csv(DATA_PATH).dropna(
    subset=FEATURES + ["median_eur"]
).copy()

train = df[df["departure_month"] < TEST_MONTH].copy()
test = df[df["departure_month"] == TEST_MONTH].copy()

if train.empty or test.empty:
    raise ValueError("Training or test data is empty.")

train_routes = set(zip(train["origin_city"], train["destination_city"]))
test_routes = list(zip(test["origin_city"], test["destination_city"]))

test["route_seen"] = [route in train_routes for route in test_routes]

preprocessor = ColumnTransformer([
    (
        "categorical",
        OrdinalEncoder(
            handle_unknown="use_encoded_value",
            unknown_value=-1,
        ),
        FEATURES,
    )
])

model = Pipeline([
    ("preprocessor", preprocessor),
    ("model", RandomForestRegressor(
        n_estimators=150,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )),
])

model.fit(train[FEATURES], train["median_eur"])

predictions = np.maximum(0, model.predict(test[FEATURES]))

baseline = DummyRegressor(strategy="median")
baseline.fit(np.zeros((len(train), 1)), train["median_eur"])
baseline_predictions = baseline.predict(np.zeros((len(test), 1)))

test["prediction"] = predictions
test["baseline_prediction"] = baseline_predictions


def report(label, subset):
    if subset.empty:
        print(f"\n{label}: no rows")
        return

    actual = subset["median_eur"]
    pred = subset["prediction"]
    base = subset["baseline_prediction"]

    mae = mean_absolute_error(actual, pred)
    baseline_mae = mean_absolute_error(actual, base)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    baseline_rmse = np.sqrt(mean_squared_error(actual, base))

    improvement = (
        (baseline_mae - mae) / baseline_mae * 100
        if baseline_mae else 0
    )

    print(f"\n{label}")
    print(f"Rows: {len(subset):,}")
    print(f"Random Forest MAE: €{mae:.2f}")
    print(f"Baseline MAE: €{baseline_mae:.2f}")
    print(f"Random Forest RMSE: €{rmse:.2f}")
    print(f"Baseline RMSE: €{baseline_rmse:.2f}")
    print(f"MAE improvement: {improvement:.2f}%")


print(f"Training rows: {len(train):,}")
print(f"Test rows: {len(test):,}")
print(f"Distinct training routes: {len(train_routes):,}")

report("ALL TEST ROUTES", test)
report("SEEN ROUTES", test[test["route_seen"]])
report("UNSEEN ROUTES", test[~test["route_seen"]])

train_origins = set(train["origin_city"])
train_destinations = set(train["destination_city"])

unseen_origin = ~test["origin_city"].isin(train_origins)
unseen_destination = ~test["destination_city"].isin(train_destinations)

report("UNSEEN ORIGIN CITY", test[unseen_origin])
report("UNSEEN DESTINATION CITY", test[unseen_destination])
report(
    "BOTH CITIES UNSEEN",
    test[unseen_origin & unseen_destination],
)
