"""Read-only access to the promoted fare model as a separate estimate layer.

The model predicts a historical monthly median one-way fare in EUR for a city
pair. It is only used when both cities and the travel month were part of its
training data; it never extrapolates and never changes or promotes models.
"""

import logging
import threading
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.services.airport_service import city_for_code

logger = logging.getLogger(__name__)
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _load_artifact(path: str) -> dict[str, Any] | None:
    try:
        import joblib  # Optional dependency: estimates are disabled without the ML stack.
    except ImportError:
        logger.info("joblib/scikit-learn not installed; fare estimates disabled.")
        return None
    model_path = Path(path)
    if not model_path.is_absolute():
        model_path = REPO_ROOT / model_path
    if not model_path.is_file():
        return None
    try:
        artifact = joblib.load(model_path)
    except Exception:  # noqa: BLE001 - a broken artifact must never break the API
        logger.exception("Could not load fare model artifact")
        return None
    if not isinstance(artifact, dict) or "model" not in artifact or artifact.get("target_transform") != "log1p":
        return None
    return artifact


def _categories(artifact: dict[str, Any]) -> dict[str, set[str]]:
    encoder = artifact["model"].named_steps["preprocessor"].named_transformers_["cities_and_month"]
    return {name: set(map(str, cats)) for name, cats in zip(encoder.feature_names_in_, encoder.categories_)}


def estimate(origin: str, destination: str, departure_date: date) -> dict[str, Any]:
    base = {
        "kind": "model_estimate",
        "label": "Model estimate — historical monthly median, not a live or guaranteed fare",
        "available": False,
    }
    with _lock:
        artifact = _load_artifact(get_settings().fare_model_path)
    if artifact is None:
        return {**base, "reason": "The fare model is not available on this server."}

    origin_city, destination_city = city_for_code(origin), city_for_code(destination)
    month = departure_date.strftime("%Y-%m")
    try:
        cats = _categories(artifact)
    except (KeyError, AttributeError):
        return {**base, "reason": "The fare model artifact has an unexpected structure."}

    if not origin_city or origin_city not in cats.get("origin_city", set()):
        return {**base, "reason": f"The model has no training data for departures from {origin}."}
    if not destination_city or destination_city not in cats.get("destination_city", set()):
        return {**base, "reason": f"The model has no training data for arrivals in {destination}."}
    if month not in cats.get("departure_month", set()):
        months = sorted(cats.get("departure_month", set()))
        span = f"{months[0]} to {months[-1]}" if months else "no months"
        return {**base, "reason": f"The model only covers departure months {span}."}

    import numpy as np
    import pandas as pd

    frame = pd.DataFrame([{"origin_city": origin_city, "destination_city": destination_city, "departure_month": month}], columns=artifact.get("features"))
    value = float(np.expm1(np.asarray(artifact["model"].predict(frame), dtype=float)[0]))
    if not np.isfinite(value) or value <= 0:
        return {**base, "reason": "The model did not return a usable estimate."}
    evaluation = artifact.get("evaluation") or {}
    return {
        **base,
        "available": True,
        "estimate": round(value, 2),
        "currency": artifact.get("currency", "EUR"),
        "trip": "one-way",
        "basis": artifact.get("target_description", "Historical monthly median one-way fare"),
        "origin_city": origin_city,
        "destination_city": destination_city,
        "month": month,
        "model_name": artifact.get("model_name"),
        "holdout_mae": evaluation.get("mae_eur"),
        "holdout_month": evaluation.get("test_month"),
    }
