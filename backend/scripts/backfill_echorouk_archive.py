"""
Gradually crawl and index the Echorouk Online archive into the internal vector store.

Usage:
    python backend/scripts/backfill_echorouk_archive.py --runs 5 --listing-pages 3 --article-pages 12
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure imports work when script is executed as a file (python scripts/...)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import async_session
from app.services.echorouk_archive_service import echorouk_archive_service


async def run(*, runs: int, listing_pages: int, article_pages: int, pause_seconds: float) -> None:
    for iteration in range(1, runs + 1):
        async with async_session() as db:
            result = await echorouk_archive_service.run_batch(
                db,
                listing_pages=listing_pages,
                article_pages=article_pages,
            )
            print(f"Run {iteration}/{runs}: {result}")
        if iteration < runs and pause_seconds > 0:
            await asyncio.sleep(pause_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--listing-pages", type=int, default=3)
    parser.add_argument("--article-pages", type=int, default=12)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    args = parser.parse_args()

    asyncio.run(
        run(
            runs=max(1, args.runs),
            listing_pages=max(1, args.listing_pages),
            article_pages=max(1, args.article_pages),
            pause_seconds=max(0.0, args.pause_seconds),
        )
    )


if __name__ == "__main__":
    main()
