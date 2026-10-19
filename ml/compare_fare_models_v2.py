
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "ml" / "data" / "raw" / "fares-by-month.csv"
TEST_MONTH = "2027-01"

df = pd.read_csv(DATA_PATH).dropna(
    subset=["origin_city", "destination_city", "departure_month", "median_eur"]
)

train = df[df["departure_month"] < TEST_MONTH].copy()
test = df[df["departure_month"] == TEST_MONTH].copy()

features = ["origin_city", "destination_city", "departure_month"]
X_train = train[features]
X_test = test[features]
y_train = train["median_eur"].astype(float)
y_test = test["median_eur"].astype(float)

results = []


def evaluate(name, predictions):
    predictions = np.maximum(0, np.asarray(predictions))
    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    results.append({"model": name, "MAE_EUR": mae, "RMSE_EUR": rmse})
    print(f"{name}: MAE €{mae:.2f} | RMSE €{rmse:.2f}")


# 1. Log-Ridge
ridge_prep = ColumnTransformer(
    [("categorical", OneHotEncoder(handle_unknown="ignore"), features)]
)
ridge = Pipeline([
    ("preprocessor", ridge_prep),
    ("model", Ridge(alpha=1.0)),
])
ridge.fit(X_train, np.log1p(y_train))
evaluate("Log-Ridge", np.expm1(ridge.predict(X_test)))


# 2. Random Forest using ordinal-encoded categorical features.
# Note: ordinal encoding gives categories arbitrary numeric codes.
# This is a baseline experiment, not necessarily the ideal encoding.
forest_prep = ColumnTransformer(
    [("categorical", OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1
    ), features)]
)
forest = Pipeline([
    ("preprocessor", forest_prep),
    ("model", RandomForestRegressor(
        n_estimators=150,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )),
])
forest.fit(X_train, y_train)
evaluate("Random Forest", forest.predict(X_test))


# 3. HistGradientBoosting with ordinal-encoded features.
boost_prep = ColumnTransformer(
    [("categorical", OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1
    ), features)]
)
boost = Pipeline([
    ("preprocessor", boost_prep),
    ("model", HistGradientBoostingRegressor(
        max_iter=150,
        learning_rate=0.08,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=42,
    )),
])
boost.fit(X_train, y_train)
evaluate("HistGradientBoosting", boost.predict(X_test))


# Median baseline
evaluate("Median Baseline", np.full(len(y_test), y_train.median()))

results_df = pd.DataFrame(results).sort_values("MAE_EUR")
print("\nSorted results (lower is better):")
print(results_df.round(2).to_string(index=False))

output_path = ROOT / "fare_model_comparison_v2.csv"
results_df.to_csv(output_path, index=False)
print(f"\nSaved comparison to: {output_path}")
