"""
Backfill indexing tables (profiles/topics/entities/chunks/vectors) for existing articles.

Usage:
    python backend/scripts/backfill_article_index.py --batch-size 200
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

# Ensure imports work when script is executed as a file (python scripts/...)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import async_session
from app.models import Article
from app.services.article_index_service import article_index_service


async def run(batch_size: int = 200) -> None:
    offset = 0
    total = 0
    while True:
        async with async_session() as db:
            result = await db.execute(
                select(Article).order_by(Article.id.asc()).offset(offset).limit(batch_size)
            )
            rows = result.scalars().all()
            if not rows:
                break
            for article in rows:
                await article_index_service.upsert_article(db, article)
                total += 1
            await db.commit()
            print(f"Indexed batch offset={offset} size={len(rows)} total={total}")
            offset += batch_size
    print(f"Done. Indexed {total} articles.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(run(batch_size=max(1, args.batch_size)))


if __name__ == "__main__":
    main()
