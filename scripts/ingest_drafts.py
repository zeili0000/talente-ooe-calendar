"""CLI helper for AI agents/maintainers: insert new event drafts from JSON into Notion."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notion_client import create_draft_page, fetch_existing_keys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest an event JSON array into Notion as Drafts/Live (with deduplication)."
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        help="Path to JSON file containing an array of event objects (reads stdin if omitted).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and check duplicates without writing to Notion.",
    )
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN", "").strip()
    database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
    if not token or not database_id:
        print("Error: NOTION_TOKEN and NOTION_DATABASE_ID must be set.", file=sys.stderr)
        return 1

    raw = Path(args.json_file).read_text(encoding="utf-8") if args.json_file else sys.stdin.read()
    items = json.loads(raw)
    if not isinstance(items, list):
        print("Error: Input JSON must be an array of event objects.", file=sys.stderr)
        return 1

    existing = fetch_existing_keys(token, database_id)
    created = 0
    skipped = 0

    for item in items:
        name = str(item.get("name", "")).strip()
        datum_start = str(item.get("datum_start") or "").strip()
        deadline = str(item.get("deadline") or "").strip()
        status = str(item.get("status") or "Draft").strip()
        if not name or (not datum_start and not deadline and status.lower() != "draft"):
            print(f"Skipping invalid entry (missing name or date/deadline): {item}", file=sys.stderr)
            skipped += 1
            continue

        ref_date = (datum_start or deadline)[:10]
        key = (" ".join(name.lower().split()), ref_date)
        if key in existing:
            print(f"Duplicate skipped: {name} ({ref_date or 'TBD'})")
            skipped += 1
            continue

        if args.dry_run:
            print(f"[DRY-RUN] Would create {status}: {name} ({datum_start or deadline or 'TBD'})")
        else:
            item.setdefault("status", "Draft")
            create_draft_page(token, database_id, item)
            print(f"Created {status}: {name} ({datum_start or deadline or 'TBD'})")
        existing.add(key)
        created += 1

    print(f"Summary: created={created}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
