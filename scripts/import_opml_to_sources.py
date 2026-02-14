#!/usr/bin/env python3
"""
Import OPML feed list into `sources` table.

Usage:
  python scripts/import_opml_to_sources.py \
    --opml-url http://news.bbc.co.uk/rss/feeds.opml \
    --db-url postgresql://echorouk:PASS@127.0.0.1:5433/echorouk_db
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

import requests
import psycopg2
from psycopg2.extras import execute_values


def parse_opml(url: str) -> list[tuple[str, str]]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    feeds: list[tuple[str, str]] = []
    for outline in root.findall(".//outline"):
        xml_url = outline.attrib.get("xmlUrl")
        if not xml_url:
            continue
        title = outline.attrib.get("title") or outline.attrib.get("text") or urlparse(xml_url).netloc
        feeds.append((title.strip(), xml_url.strip()))
    # dedup by URL
    uniq = {}
    for title, xml_url in feeds:
        uniq[xml_url] = title
    return [(title, xml_url) for xml_url, title in uniq.items()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opml-url", required=True)
    ap.add_argument("--db-url", required=True)
    ap.add_argument("--prefix", default="OPML")
    args = ap.parse_args()

    feeds = parse_opml(args.opml_url)
    if not feeds:
        print("No feeds found in OPML.")
        return 1

    rows = []
    now = datetime.utcnow()
    for title, xml_url in feeds:
        name = f"{args.prefix} - {title}"[:255]
        rows.append((name, "rss", xml_url, xml_url, "en", "aggregator", "medium", 4, True, now, now))

    conn = psycopg2.connect(args.db_url)
    try:
        with conn, conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO sources
                (name, method, url, rss_url, language, source_type, credibility, priority, enabled, created_at, updated_at)
                VALUES %s
                ON CONFLICT (url) DO UPDATE
                SET rss_url = EXCLUDED.rss_url, enabled = true, updated_at = now()
                """,
                rows,
            )
        print(f"Imported/updated {len(rows)} feeds.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

