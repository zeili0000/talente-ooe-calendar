"""Build entrypoint: fetch Notion events, emit dist/*.ics + events.json + index.html, validate all outputs."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from icalendar import Calendar

from src.html_builder import build_index_html
from src.ics_builder import build_calendar, slugify_category
from src.notion_client import EventRecord, fetch_database_schema, fetch_events


def _event_to_json(ev: EventRecord) -> dict[str, object]:
    return {
        "page_id": ev.page_id,
        "last_edited_time": ev.last_edited_time,
        "name": ev.name,
        "datum_start": ev.datum_start,
        "datum_end": ev.datum_end,
        "status": ev.status,
        "categories": list(ev.categories),
        "category_slugs": [slugify_category(c) for c in ev.categories],
        "grade_min": ev.grade_min,
        "grade_max": ev.grade_max,
        "organizer": ev.organizer,
        "location": ev.location,
        "cost": ev.cost,
        "link": ev.link,
        "description": ev.description,
        "deadline": ev.deadline,
        "create_deadline_event": ev.create_deadline_event,
    }


def validate_dist(dist_dir: Path) -> None:
    """Re-parse every generated .ics and events.json to prevent deploying corrupt feeds."""
    ics_files = sorted(dist_dir.glob("*.ics"))
    if not ics_files:
        raise RuntimeError("Validation failed: no .ics files were generated.")
    for ics_path in ics_files:
        raw = ics_path.read_bytes()
        if not raw.strip():
            raise RuntimeError(f"Validation failed: {ics_path.name} is empty.")
        cal = Calendar.from_ical(raw)
        if cal.get("VERSION") != "2.0":
            raise RuntimeError(f"Validation failed: {ics_path.name} missing VERSION:2.0.")

    events_json = dist_dir / "events.json"
    parsed = json.loads(events_json.read_text(encoding="utf-8"))
    if "events" not in parsed or not isinstance(parsed["events"], list):
        raise RuntimeError("Validation failed: events.json malformed.")
    if len(parsed["events"]) == 0:
        raise RuntimeError("Validation failed: 0 Live/Cancelled events returned; refusing to overwrite feeds.")


def build_dist(
    events: list[EventRecord],
    schema_categories: list[str],
    dist_dir: Path,
    worker_base_url: str = "",
) -> None:
    """Generate all static .ics feeds, events.json, and index.html in dist_dir."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)

    # Combine schema options with any category present on events, preserving schema order
    ordered_cats: list[str] = list(schema_categories)
    for ev in events:
        for cat in ev.categories:
            if cat not in ordered_cats:
                ordered_cats.append(cat)

    (dist_dir / "all.ics").write_bytes(
        build_calendar(events, "Talente OÖ & MINT Kalender", include_deadlines=False, now_utc=now_utc)
    )
    (dist_dir / "all-mit-fristen.ics").write_bytes(
        build_calendar(events, "Talente OÖ & MINT (inkl. Fristen)", include_deadlines=True, now_utc=now_utc)
    )
    (dist_dir / "fristen.ics").write_bytes(
        build_calendar(events, "Talente OÖ & MINT - Anmeldefristen", deadlines_only=True, now_utc=now_utc)
    )

    cat_summaries: list[dict[str, object]] = []
    for cat_name in ordered_cats:
        slug = slugify_category(cat_name)
        matching = [ev for ev in events if cat_name in ev.categories]
        (dist_dir / f"{slug}.ics").write_bytes(
            build_calendar(matching, f"Kalender: {cat_name}", include_deadlines=False, now_utc=now_utc)
        )
        cat_summaries.append({"name": cat_name, "slug": slug, "count": len(matching)})

    events_payload = {
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": cat_summaries,
        "events": [_event_to_json(ev) for ev in events],
    }
    (dist_dir / "events.json").write_text(
        json.dumps(events_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (dist_dir / "index.html").write_text(
        build_index_html(cat_summaries, events_payload, worker_base_url=worker_base_url),
        encoding="utf-8",
    )
    validate_dist(dist_dir)


def main() -> int:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
    worker_base_url = os.environ.get("WORKER_BASE_URL", "").strip()
    if not token or not database_id:
        print("Error: NOTION_TOKEN and NOTION_DATABASE_ID must be set.", file=sys.stderr)
        return 1

    schema_cats = fetch_database_schema(token, database_id)
    events = fetch_events(token, database_id)
    dist_dir = Path("dist")
    build_dist(events, schema_cats, dist_dir, worker_base_url=worker_base_url)
    print(f"Built {len(events)} events across {len(schema_cats)} categories into {dist_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
