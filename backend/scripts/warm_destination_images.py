"""Fill the destination photo cache for every destination city.

Optional: the website looks photos up on demand. Running this once after a
deployment (or from a weekly scheduled job) means visitors rarely wait for a
lookup. Cities with a fresh cache entry are skipped, so re-running is cheap.

Usage (from the backend directory, with WIKIMEDIA_USER_AGENT set in .env):
  python scripts/warm_destination_images.py [--limit N] [--pause SECONDS]
"""

import argparse
import sys
import time
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.services import destination_service, image_service  # noqa: E402

CHUNK = 24


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="only the first N cities (by popularity)")
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between batches, to stay well under rate limits")
    args = parser.parse_args()

    init_db()
    cities = list(destination_service.cities())
    cities.sort(key=lambda c: destination_service.POPULARITY.get(c.key, 10_000))
    if args.limit:
        cities = cities[: args.limit]
    finder = partial(image_service.lookup, commons_limit=CHUNK)
    totals = {"photo": 0, "none": 0, "pending": 0}
    for i in range(0, len(cities), CHUNK):
        with SessionLocal() as db:
            rows = image_service.images_for(db, cities[i:i + CHUNK], finder=finder)
        for row in rows:
            totals["photo" if row["available"] else "pending" if row.get("pending") else "none"] += 1
        print(f"{min(i + CHUNK, len(cities))}/{len(cities)}  {totals}", flush=True)
        time.sleep(args.pause)
    print("Done. Pending cities could not be checked (rate limit or network) and will be retried on demand.")


if __name__ == "__main__":
    main()
