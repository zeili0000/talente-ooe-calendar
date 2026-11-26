"""Tests for RFC-5545 generation, DST handling, deadlines, region filtering, validation gate, and Worker parity."""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

from src.build import build_dist, validate_dist
from src.ics_builder import build_calendar, slugify_category
from src.notion_client import EventRecord

VIENNA = ZoneInfo("Europe/Vienna")


def _sample_events() -> list[EventRecord]:
    return [
        EventRecord(
            page_id="11111111-1111-1111-1111-111111111111",
            last_edited_time="2026-11-20T10:00:00.000Z",
            name="Winter Workshop KI",
            datum_start="2027-02-04T13:00:00+01:00",
            datum_end=None,  # tests default +2h duration
            status="Live",
            categories=("Talente OÖ", "MINT & Tech"),
            grade_min=11,
            grade_max=13,
            organizer="FH OÖ Workshop",
            location="FH OÖ Campus Hagenberg",
            cost="0,00 €",
            link="https://anmeldung.talente-ooe.at/event?event=1246",
            description="Logische Grundlagen der KI.",
            deadline="2027-01-14",
            create_deadline_event=True,
            region="OÖ / Online",
        ),
        EventRecord(
            page_id="22222222-2222-2222-2222-222222222222",
            last_edited_time="2026-11-20T10:00:00.000Z",
            name="ÖMO Bundeswettbewerb Finale",
            datum_start="2027-05-26T08:30:00+02:00",
            datum_end="2027-05-27T13:00:00+02:00",
            status="Live",
            categories=("Olympiade: Mathe",),
            grade_min=9,
            grade_max=13,
            organizer="ÖMO",
            location="Raach am Hochgebirge",
            cost="",
            link="https://www.oemo.at/",
            description="Bundeswettbewerb Finale.",
            deadline=None,
            create_deadline_event=False,
            region="Österreich",
        ),
        EventRecord(
            page_id="33333333-3333-3333-3333-333333333333",
            last_edited_time="2026-11-20T10:00:00.000Z",
            name="IMO Budapest",
            datum_start="2027-07-19",
            datum_end="2027-07-26",
            status="Live",
            categories=("Olympiade: Mathe",),
            grade_min=9,
            grade_max=13,
            organizer="IMO",
            location="Budapest",
            cost="",
            link="https://www.oemo.at/",
            description="Internationale Mathematik-Olympiade.",
            deadline="2027-06-01",
            create_deadline_event=False,  # suppressed deadline event
            region="International",
        ),
        EventRecord(
            page_id="44444444-4444-4444-4444-444444444444",
            last_edited_time="2026-11-20T10:00:00.000Z",
            name="Abgesagtes Camp",
            datum_start="2027-03-10",
            datum_end=None,
            status="Cancelled",
            categories=("CanSat",),
            grade_min=9,
            grade_max=12,
            organizer="ESERO",
            location="Linz",
            cost="",
            link=None,
            description="",
            deadline=None,
            create_deadline_event=False,
            region="OÖ / Online",
        ),
        EventRecord(
            page_id="55555555-5555-5555-5555-555555555555",
            last_edited_time="2026-11-20T10:00:00.000Z",
            name="voestalpine Sommerpraktikum",
            datum_start=None,
            datum_end=None,
            status="Live",
            categories=("Praktika & Stipendien",),
            grade_min=9,
            grade_max=13,
            organizer="voestalpine",
            location="Linz",
            cost="",
            link="https://www.voestalpine.com/group/de/jobs/studierende-schueler/",
            description="Sommerpraktikum in Technik und IT.",
            deadline="2027-01-31",
            create_deadline_event=True,
            region="OÖ / Online",
        ),
    ]


def test_slugify_category() -> None:
    assert slugify_category("Talente OÖ") == "talente-ooe"
    assert slugify_category("Olympiade: Mathe") == "olympiade-mathe"
    assert slugify_category("MINT & Tech") == "mint-tech"
    assert slugify_category("Straße & Spaß") == "strasse-spass"


def test_ics_dst_default_duration_all_day_and_cancelled() -> None:
    raw = build_calendar(_sample_events(), "Test Feed", include_deadlines=True)
    cal = Calendar.from_ical(raw)
    assert cal.get("VERSION") == "2.0"

    vevents = {str(c.get("UID")): c for c in cal.walk("VEVENT")}
    # 4 main events (5555 has no datum_start) + 2 deadline events (1111, 5555)
    assert len(vevents) == 6

    # Winter timed event with missing end -> +2h in CET (+01:00)
    winter = vevents["11111111-1111-1111-1111-111111111111@talente-ooe-cal"]
    assert winter.decoded("DTSTART") == datetime(2027, 2, 4, 13, 0, tzinfo=VIENNA)
    assert winter.decoded("DTEND") == datetime(2027, 2, 4, 15, 0, tzinfo=VIENNA)
    assert "Anmeldeschluss: 14.01.2027" in str(winter.get("DESCRIPTION"))

    # Deadline-only row (5555) creates only the -deadline VEVENT even when include_deadlines=False
    raw_no_dl = build_calendar(_sample_events(), "Test No Deadlines", include_deadlines=False)
    vevents_no_dl = {str(c.get("UID")): c for c in Calendar.from_ical(raw_no_dl).walk("VEVENT")}
    assert "55555555-5555-5555-5555-555555555555-deadline@talente-ooe-cal" in vevents_no_dl
    assert "55555555-5555-5555-5555-555555555555@talente-ooe-cal" not in vevents_no_dl
    assert "11111111-1111-1111-1111-111111111111-deadline@talente-ooe-cal" not in vevents_no_dl

    # Summer timed event (CEST +02:00)
    summer = vevents["22222222-2222-2222-2222-222222222222@talente-ooe-cal"]
    assert summer.decoded("DTSTART") == datetime(2027, 5, 26, 8, 30, tzinfo=VIENNA)

    # Multi-day all-day event: exclusive DTEND (+1 day -> 2027-07-27)
    all_day = vevents["33333333-3333-3333-3333-333333333333@talente-ooe-cal"]
    assert all_day.decoded("DTSTART") == date(2027, 7, 19)
    assert all_day.decoded("DTEND") == date(2027, 7, 27)

    # Cancelled single-day event
    cancelled = vevents["44444444-4444-4444-4444-444444444444@talente-ooe-cal"]
    assert str(cancelled.get("STATUS")) == "CANCELLED"
    assert str(cancelled.get("SUMMARY")).startswith("[ABGESAGT] ")


def test_build_dist_and_validation_gate(tmp_path: Path) -> None:
    events = _sample_events()
    schema_cats = ["Talente OÖ", "Olympiade: Mathe", "CanSat", "Praktika & Stipendien", "Empty Category"]
    build_dist(events, schema_cats, tmp_path, worker_base_url="https://cal.example.workers.dev")

    assert (tmp_path / "all.ics").exists()
    assert (tmp_path / "fristen.ics").exists()
    assert (tmp_path / "all-mit-fristen.ics").exists()
    assert (tmp_path / "empty-category.ics").exists()
    assert (tmp_path / "events.json").exists()
    assert (tmp_path / "index.html").exists()

    (tmp_path / "events.json").write_text('{"events": []}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="0 Live/Cancelled events"):
        validate_dist(tmp_path)


def test_cloudflare_worker_rfc5545_parity_and_region(tmp_path: Path) -> None:
    events = _sample_events()
    schema_cats = ["Talente OÖ", "Olympiade: Mathe", "CanSat", "Praktika & Stipendien"]
    build_dist(events, schema_cats, tmp_path)

    events_json_path = tmp_path / "events.json"
    worker_path = Path("worker/src/index.js").resolve().as_uri()

    # 1. Legacy URL without region segment (all regions)
    js_legacy = (
        f"import fs from 'node:fs';"
        f"import {{ generateIcsFromEvents, parseParamsFromUrl }} from '{worker_path}';"
        f"const data = JSON.parse(fs.readFileSync({json.dumps(str(events_json_path))}, 'utf8'));"
        f"const params = parseParamsFromUrl(new URL('https://example.workers.dev/cal/g11/d1/talente-ooe+olympiade-mathe.ics'));"
        f"process.stdout.write(generateIcsFromEvents(data, params));"
    )
    proc = subprocess.run(["node", "--input-type=module", "-e", js_legacy], capture_output=True, check=True)
    vevents = {str(c.get("UID")): c for c in Calendar.from_ical(proc.stdout).walk("VEVENT")}
    assert "11111111-1111-1111-1111-111111111111@talente-ooe-cal" in vevents
    assert "22222222-2222-2222-2222-222222222222@talente-ooe-cal" in vevents
    assert "33333333-3333-3333-3333-333333333333@talente-ooe-cal" in vevents
    assert "44444444-4444-4444-4444-444444444444@talente-ooe-cal" not in vevents

    # 2. Region URL (rooe) + deadline-only event (5555)
    js_region = (
        f"import fs from 'node:fs';"
        f"import {{ generateIcsFromEvents, parseParamsFromUrl }} from '{worker_path}';"
        f"const data = JSON.parse(fs.readFileSync({json.dumps(str(events_json_path))}, 'utf8'));"
        f"const params = parseParamsFromUrl(new URL('https://example.workers.dev/cal/g11/d0/rooe/talente-ooe_praktika-stipendien_olympiade-mathe.ics'));"
        f"process.stdout.write(generateIcsFromEvents(data, params));"
    )
    proc_r = subprocess.run(["node", "--input-type=module", "-e", js_region], capture_output=True, check=True)
    vevents_r = {str(c.get("UID")): c for c in Calendar.from_ical(proc_r.stdout).walk("VEVENT")}
    assert "11111111-1111-1111-1111-111111111111@talente-ooe-cal" in vevents_r
    assert "55555555-5555-5555-5555-555555555555-deadline@talente-ooe-cal" in vevents_r
    assert "22222222-2222-2222-2222-222222222222@talente-ooe-cal" not in vevents_r
    assert "33333333-3333-3333-3333-333333333333@talente-ooe-cal" not in vevents_r
