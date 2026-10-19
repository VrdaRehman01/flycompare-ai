
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "ml" / "data" / "raw"
SNAPSHOT_DIR = PROJECT_ROOT / "ml" / "data" / "snapshots"

BASE_URL = (
    "https://huggingface.co/datasets/"
    "DeusHorizon/flight-fare-history/resolve/main"
)

FILES = ["fares-by-month.csv", "routes.csv", "summary.json"]

REQUIRED_COLUMNS = [
    "origin_city",
    "destination_city",
    "departure_month",
    "observations",
    "median_eur",
    "p10_eur",
    "min_eur",
]

ROUTE_MONTH_KEY = [
    "origin_city",
    "destination_city",
    "departure_month",
]


def download_file(session: requests.Session, filename: str, target: Path) -> None:
    url = f"{BASE_URL}/{filename}"
    response = session.get(url, timeout=(15, 120))
    response.raise_for_status()
    target.write_bytes(response.content)

    if target.stat().st_size == 0:
        raise ValueError(f"Downloaded file is empty: {filename}")


def validate_dataset(data_dir: Path) -> dict:
    fares_path = data_dir / "fares-by-month.csv"
    routes_path = data_dir / "routes.csv"
    summary_path = data_dir / "summary.json"

    fares = pd.read_csv(fares_path)
    routes = pd.read_csv(routes_path)

    with summary_path.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    missing_columns = set(REQUIRED_COLUMNS) - set(fares.columns)
    if missing_columns:
        raise ValueError(f"Fare dataset is missing columns: {sorted(missing_columns)}")

    if fares.empty:
        raise ValueError("Fare dataset contains no rows.")

    if routes.empty:
        raise ValueError("Routes dataset contains no rows.")

    if fares[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError("Fare dataset contains missing required values.")

    if fares.duplicated(subset=ROUTE_MONTH_KEY).any():
        raise ValueError("Duplicate origin/destination/departure-month rows found.")

    numeric_columns = [
        "observations",
        "median_eur",
        "p10_eur",
        "min_eur",
    ]

    for column in numeric_columns:
        fares[column] = pd.to_numeric(fares[column], errors="raise")

    if not fares[numeric_columns].map(lambda value: pd.notna(value) and abs(value) != float("inf")).all().all():
        raise ValueError("Numeric columns contain invalid or infinite values.")

    if (fares["observations"] < 1).any():
        raise ValueError("Observation counts must be positive.")

    fare_columns = ["median_eur", "p10_eur", "min_eur"]
    if (fares[fare_columns] <= 0).any().any():
        raise ValueError("Fare values must be positive.")

    if (fares["p10_eur"] > fares["median_eur"]).any():
        raise ValueError("10th-percentile fare exceeds median fare.")

    if (fares["min_eur"] > fares["median_eur"]).any():
        raise ValueError("Minimum fare exceeds median fare.")

    if fares["departure_month"].astype(str).str.fullmatch(r"\d{4}-\d{2}").all() is False:
        raise ValueError("Departure months must use YYYY-MM format.")

    if not isinstance(summary, dict):
        raise ValueError("Summary JSON must contain an object.")

    return {
        "fare_rows": len(fares),
        "route_rows": len(routes),
        "departure_months": sorted(fares["departure_month"].astype(str).unique().tolist()),
        "summary": summary,
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="flycompare-update-") as temp:
        temp_dir = Path(temp)

        with requests.Session() as session:
            session.headers.update(
                {"User-Agent": "FlyCompare-AI-Dataset-Updater/1.0"}
            )
            for filename in FILES:
                print(f"Downloading {filename}...")
                download_file(session, filename, temp_dir / filename)

        result = validate_dataset(temp_dir)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        snapshot = SNAPSHOT_DIR / today
        if snapshot.exists():
            snapshot = SNAPSHOT_DIR / (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
            )

        # Keep a snapshot of the newly validated publisher files.
        shutil.copytree(temp_dir, snapshot)

        # Back up the currently installed files so a failed replacement can roll back.
        backup_dir = Path(tempfile.mkdtemp(prefix="flycompare-backup-"))
        try:
            for filename in FILES:
                current = RAW_DIR / filename
                if current.exists():
                    shutil.copy2(current, backup_dir / filename)

            try:
                for filename in FILES:
                    shutil.copy2(temp_dir / filename, RAW_DIR / filename)
            except Exception:
                for filename in FILES:
                    backup = backup_dir / filename
                    current = RAW_DIR / filename
                    if backup.exists():
                        shutil.copy2(backup, current)
                    elif current.exists():
                        current.unlink()
                raise
        finally:
            shutil.rmtree(backup_dir, ignore_errors=True)

    print("Dataset update completed successfully.")
    print(f"Validated fare rows: {result['fare_rows']:,}")
    print(f"Validated route rows: {result['route_rows']:,}")
    print(f"Departure months: {', '.join(result['departure_months'])}")
    print(f"Snapshot saved: {snapshot}")
    print("Source: DeusHorizon/flight-fare-history on Hugging Face.")


if __name__ == "__main__":
    main()
