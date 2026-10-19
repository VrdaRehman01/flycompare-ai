
from pathlib import Path

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

# Use the same final month as our previous holdout evaluation.
TEST_MONTH = "2027-01"

# Reproduce the leading candidate: Ridge trained on log-transformed fares.
ALPHA = 1.0

df = pd.read_csv(DATA_PATH)

required_columns = {
    "origin_city",
    "destination_city",
    "departure_month",
    "median_eur",
}

missing_columns = required_columns - set(df.columns)
if missing_columns:
    raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

df = df.dropna(subset=list(required_columns)).copy()
df["median_eur"] = pd.to_numeric(df["median_eur"], errors="raise")

train = df[df["departure_month"] < TEST_MONTH].copy()
test = df[df["departure_month"] == TEST_MONTH].copy()

if train.empty or test.empty:
    raise ValueError("Training or test data is empty. Check TEST_MONTH.")

# A route is directional: A -> B is distinct from B -> A.
train_routes = set(zip(train["origin_city"], train["destination_city"]))

test_route_keys = list(zip(test["origin_city"], test["destination_city"]))
test["route_seen_in_training"] = [
    route in train_routes for route in test_route_keys
]

feature_columns = [
    "origin_city",
    "destination_city",
    "departure_month",
]

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            feature_columns,
        )
    ]
)

model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("regressor", Ridge(alpha=ALPHA)),
    ]
)

model.fit(train[feature_columns], np.log1p(train["median_eur"]))

# Convert log predictions back to euros.
predictions = np.expm1(model.predict(test[feature_columns]))
predictions = np.maximum(predictions, 0)

# Baseline: predict the median fare from the training set.
baseline = DummyRegressor(strategy="median")
baseline.fit(
    np.zeros((len(train), 1)),
    train["median_eur"],
)
baseline_predictions = baseline.predict(np.zeros((len(test), 1)))


def report_results(label, mask):
    subset = test.loc[mask]
    if subset.empty:
        print(f"\n{label}: no rows")
        return

    indices = subset.index
    y_true = subset["median_eur"].to_numpy()
    y_pred = predictions[test.index.get_indexer(indices)]
    y_base = baseline_predictions[test.index.get_indexer(indices)]

    model_mae = mean_absolute_error(y_true, y_pred)
    baseline_mae = mean_absolute_error(y_true, y_base)
    model_rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    baseline_rmse = np.sqrt(mean_squared_error(y_true, y_base))

    improvement = (
        (baseline_mae - model_mae) / baseline_mae * 100
        if baseline_mae
        else 0
    )

    print(f"\n{label}")
    print("-" * len(label))
    print(f"Rows: {len(subset):,}")
    print(f"Model MAE: €{model_mae:.2f}")
    print(f"Baseline MAE: €{baseline_mae:.2f}")
    print(f"Model RMSE: €{model_rmse:.2f}")
    print(f"Baseline RMSE: €{baseline_rmse:.2f}")
    print(f"MAE improvement: {improvement:.2f}%")


print(f"Training rows: {len(train):,}")
print(f"Test rows: {len(test):,}")
print(f"Training routes: {len(train_routes):,}")
print(f"Test routes: {len(set(test_route_keys)):,}")

report_results("ALL TEST ROUTES", np.ones(len(test), dtype=bool))
report_results(
    "ROUTES SEEN IN TRAINING",
    test["route_seen_in_training"].to_numpy(),
)
report_results(
    "ROUTES NOT SEEN IN TRAINING",
    ~test["route_seen_in_training"].to_numpy(),
)

# Also inspect unseen origin and destination cities separately.
train_origins = set(train["origin_city"])
train_destinations = set(train["destination_city"])

unseen_origin = ~test["origin_city"].isin(train_origins).to_numpy()
unseen_destination = ~test["destination_city"].isin(train_destinations).to_numpy()

report_results("UNSEEN ORIGIN CITY", unseen_origin)
report_results("UNSEEN DESTINATION CITY", unseen_destination)
report_results(
    "BOTH ORIGIN AND DESTINATION UNSEEN",
    unseen_origin & unseen_destination,
)
