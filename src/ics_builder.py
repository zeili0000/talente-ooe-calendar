"""RFC-5545 .ics calendar generator with Europe/Vienna timezone and deadline support."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from src.notion_client import EventRecord, format_iso_date_de, parse_notion_temporal

VIENNA_TZ_NAME = "Europe/Vienna"
VIENNA_TZ = ZoneInfo(VIENNA_TZ_NAME)
UID_DOMAIN = "talente-ooe-cal"


def slugify_category(name: str) -> str:
    """Convert a German category name into a clean URL-safe filename slug."""
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
    }
    text = name
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "sonstiges"


def _build_description(ev: EventRecord) -> str:
    lines: list[str] = []
    if ev.deadline:
        lines.append(f"Anmeldeschluss: {format_iso_date_de(ev.deadline)}")
    if ev.grade_min is not None and ev.grade_max is not None:
        lines.append(f"Schulstufe: {ev.grade_min}.-{ev.grade_max}. Schulstufe")
    elif ev.grade_min is not None:
        lines.append(f"Schulstufe: ab {ev.grade_min}. Schulstufe")
    elif ev.grade_max is not None:
        lines.append(f"Schulstufe: bis {ev.grade_max}. Schulstufe")
    if ev.cost:
        lines.append(f"Kosten: {ev.cost}")
    if ev.organizer:
        lines.append(f"Veranstalter: {ev.organizer}")
    if ev.categories:
        lines.append(f"Kategorien: {', '.join(ev.categories)}")
    if ev.description:
        if lines:
            lines.append("")
        lines.append(ev.description)
    if ev.link:
        if lines:
            lines.append("")
        lines.append(f"Infos & Anmeldung: {ev.link}")
    return "\n".join(lines).strip()


def _parse_last_modified(ev: EventRecord, fallback_utc: datetime) -> datetime:
    if not ev.last_edited_time:
        return fallback_utc
    dt = datetime.fromisoformat(ev.last_edited_time.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _create_main_vevent(
    ev: EventRecord,
    now_utc: datetime,
    default_duration_hours: int,
) -> Event:
    vevent = Event()
    vevent.add("uid", f"{ev.page_id}@{UID_DOMAIN}")
    vevent.add("dtstamp", now_utc)
    vevent.add("last-modified", _parse_last_modified(ev, now_utc))

    is_cancelled = ev.status.lower() == "cancelled"
    summary = f"[ABGESAGT] {ev.name}" if is_cancelled else ev.name
    vevent.add("summary", summary)
    vevent.add("status", "CANCELLED" if is_cancelled else "CONFIRMED")

    start_val = parse_notion_temporal(ev.datum_start, VIENNA_TZ_NAME)
    end_val = parse_notion_temporal(ev.datum_end, VIENNA_TZ_NAME) if ev.datum_end else None

    if isinstance(start_val, datetime):
        if isinstance(end_val, datetime):
            dtend = end_val
        elif isinstance(end_val, date):
            dtend = datetime.combine(end_val, time(23, 59), tzinfo=VIENNA_TZ)
        else:
            dtend = start_val + timedelta(hours=default_duration_hours)
        vevent.add("dtstart", start_val)
        vevent.add("dtend", dtend)
    else:
        # All-day event: RFC 5545 DTEND is exclusive (+1 day)
        end_date = end_val.date() if isinstance(end_val, datetime) else (end_val or start_val)
        if end_date < start_val:
            end_date = start_val
        vevent.add("dtstart", start_val)
        vevent.add("dtend", end_date + timedelta(days=1))

    if ev.location:
        vevent.add("location", ev.location)
    desc = _build_description(ev)
    if desc:
        vevent.add("description", desc)
    if ev.link:
        vevent.add("url", ev.link)
    if ev.categories:
        vevent.add("categories", list(ev.categories))

    return vevent


def _create_deadline_vevent(ev: EventRecord, now_utc: datetime) -> Event | None:
    if not ev.deadline or not ev.create_deadline_event:
        return None
    d = date.fromisoformat(ev.deadline[:10])
    vevent = Event()
    vevent.add("uid", f"{ev.page_id}-deadline@{UID_DOMAIN}")
    vevent.add("dtstamp", now_utc)
    vevent.add("last-modified", _parse_last_modified(ev, now_utc))

    is_cancelled = ev.status.lower() == "cancelled"
    summary = f"[ABGESAGT] [FRIST] {ev.name}" if is_cancelled else f"[FRIST] {ev.name}"
    vevent.add("summary", summary)
    vevent.add("status", "CANCELLED" if is_cancelled else "CONFIRMED")
    vevent.add("dtstart", d)
    vevent.add("dtend", d + timedelta(days=1))

    lines = [
        f"Anmeldeschluss für: {ev.name}",
        f"Veranstaltungstermin: {format_iso_date_de(ev.datum_start)}",
    ]
    if ev.grade_min is not None and ev.grade_max is not None:
        lines.append(f"Schulstufe: {ev.grade_min}.-{ev.grade_max}. Schulstufe")
    if ev.organizer:
        lines.append(f"Veranstalter: {ev.organizer}")
    if ev.link:
        lines.append(f"Anmeldung: {ev.link}")
    vevent.add("description", "\n".join(lines))
    if ev.link:
        vevent.add("url", ev.link)
    return vevent


def build_calendar(
    events: list[EventRecord],
    cal_name: str,
    include_deadlines: bool = False,
    deadlines_only: bool = False,
    default_duration_hours: int = 2,
    now_utc: datetime | None = None,
) -> bytes:
    """Serialize a list of EventRecords into an RFC-5545 compliant .ics payload."""
    stamp = now_utc or datetime.now(timezone.utc)
    cal = Calendar()
    cal.add("prodid", "-//Talente OOE Community//Event Calendar//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", cal_name)
    cal.add("x-wr-timezone", VIENNA_TZ_NAME)
    cal.add("refresh-interval", timedelta(hours=12), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", "PT12H")

    for ev in events:
        if not deadlines_only:
            cal.add_component(_create_main_vevent(ev, stamp, default_duration_hours))
        if include_deadlines or deadlines_only:
            dl_event = _create_deadline_vevent(ev, stamp)
            if dl_event is not None:
                cal.add_component(dl_event)

    cal.add_missing_timezones()
    return cal.to_ical()
