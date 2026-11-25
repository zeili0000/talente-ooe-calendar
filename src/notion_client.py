"""Minimal Notion REST API client for reading events and writing drafts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


@dataclass(frozen=True)
class EventRecord:
    """Normalized event row fetched from the Notion calendar database."""

    page_id: str
    last_edited_time: str
    name: str
    datum_start: str
    datum_end: str | None
    status: str
    categories: tuple[str, ...]
    grade_min: int | None
    grade_max: int | None
    organizer: str
    location: str
    cost: str
    link: str | None
    description: str
    deadline: str | None
    create_deadline_event: bool


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _plain_text(rich_text_items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in rich_text_items).strip()


def fetch_database_schema(token: str, database_id: str, client: httpx.Client | None = None) -> list[str]:
    """Return all configured Multi-Select options for the 'Kategorie' column."""
    own_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        resp = http.get(f"{NOTION_API_BASE}/databases/{database_id}", headers=_headers(token))
        resp.raise_for_status()
        data = resp.json()
        cat_prop = data.get("properties", {}).get("Kategorie", {})
        options = cat_prop.get("multi_select", {}).get("options", [])
        return [opt["name"] for opt in options if opt.get("name")]
    finally:
        if own_client:
            http.close()


def _parse_page(page: dict[str, Any]) -> EventRecord | None:
    props = page.get("properties", {})
    name = _plain_text(props.get("Name", {}).get("title", []))
    datum = props.get("Datum", {}).get("date")
    if not name or not datum or not datum.get("start"):
        return None

    status_obj = props.get("Status", {}).get("select")
    status = status_obj.get("name", "Draft") if status_obj else "Draft"

    cats = tuple(
        opt["name"]
        for opt in props.get("Kategorie", {}).get("multi_select", [])
        if opt.get("name")
    )

    g_min = props.get("Schulstufe von", {}).get("number")
    g_max = props.get("Schulstufe bis", {}).get("number")

    deadline_obj = props.get("Anmeldefrist", {}).get("date")
    deadline = deadline_obj.get("start") if deadline_obj else None

    frist_checkbox = props.get("Frist-Event", {}).get("checkbox", False)

    return EventRecord(
        page_id=page["id"],
        last_edited_time=page.get("last_edited_time", ""),
        name=name,
        datum_start=datum["start"],
        datum_end=datum.get("end"),
        status=status,
        categories=cats,
        grade_min=int(g_min) if g_min is not None else None,
        grade_max=int(g_max) if g_max is not None else None,
        organizer=_plain_text(props.get("Veranstalter", {}).get("rich_text", [])),
        location=_plain_text(props.get("Ort", {}).get("rich_text", [])),
        cost=_plain_text(props.get("Kosten", {}).get("rich_text", [])),
        link=props.get("Link", {}).get("url") or None,
        description=_plain_text(props.get("Beschreibung", {}).get("rich_text", [])),
        deadline=deadline,
        create_deadline_event=bool(frist_checkbox and deadline),
    )


def fetch_events(
    token: str,
    database_id: str,
    statuses: tuple[str, ...] = ("Live", "Cancelled"),
    client: httpx.Client | None = None,
) -> list[EventRecord]:
    """Fetch all paginated events matching the given Notion Status values."""
    own_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        filter_payload: dict[str, Any] = {
            "or": [{"property": "Status", "select": {"equals": s}} for s in statuses]
        }
        events: list[EventRecord] = []
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {
                "filter": filter_payload,
                "sorts": [{"property": "Datum", "direction": "ascending"}],
                "page_size": 100,
            }
            if cursor:
                body["start_cursor"] = cursor
            resp = http.post(
                f"{NOTION_API_BASE}/databases/{database_id}/query",
                headers=_headers(token),
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()
            for page in payload.get("results", []):
                parsed = _parse_page(page)
                if parsed is not None:
                    events.append(parsed)
            if not payload.get("has_more"):
                break
            cursor = payload.get("next_cursor")
        return events
    finally:
        if own_client:
            http.close()


def fetch_existing_keys(token: str, database_id: str, client: httpx.Client | None = None) -> set[tuple[str, str]]:
    """Fetch normalized (lowercase name, YYYY-MM-DD start) pairs for deduplication."""
    own_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        keys: set[tuple[str, str]] = set()
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            resp = http.post(
                f"{NOTION_API_BASE}/databases/{database_id}/query",
                headers=_headers(token),
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()
            for page in payload.get("results", []):
                parsed = _parse_page(page)
                if parsed is not None:
                    keys.add((" ".join(parsed.name.lower().split()), parsed.datum_start[:10]))
            if not payload.get("has_more"):
                break
            cursor = payload.get("next_cursor")
        return keys
    finally:
        if own_client:
            http.close()


def create_draft_page(
    token: str,
    database_id: str,
    event_data: dict[str, Any],
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Create a single Draft event page in the Notion database."""
    own_client = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        datum_obj: dict[str, Any] = {"start": event_data["datum_start"]}
        if event_data.get("datum_end"):
            datum_obj["end"] = event_data["datum_end"]

        props: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": event_data["name"]}}]},
            "Datum": {"date": datum_obj},
            "Status": {"select": {"name": event_data.get("status", "Draft")}},
            "Frist-Event": {"checkbox": bool(event_data.get("deadline"))},
        }
        if event_data.get("categories"):
            props["Kategorie"] = {
                "multi_select": [{"name": c} for c in event_data["categories"]]
            }
        if event_data.get("deadline"):
            props["Anmeldefrist"] = {"date": {"start": str(event_data["deadline"])[:10]}}
        if event_data.get("grade_min") is not None:
            props["Schulstufe von"] = {"number": int(event_data["grade_min"])}
        if event_data.get("grade_max") is not None:
            props["Schulstufe bis"] = {"number": int(event_data["grade_max"])}
        for key, prop_name in (
            ("organizer", "Veranstalter"),
            ("location", "Ort"),
            ("cost", "Kosten"),
            ("description", "Beschreibung"),
        ):
            val = event_data.get(key)
            if val:
                props[prop_name] = {"rich_text": [{"text": {"content": str(val)[:2000]}}]}
        if event_data.get("link"):
            props["Link"] = {"url": event_data["link"]}

        resp = http.post(
            f"{NOTION_API_BASE}/pages",
            headers=_headers(token),
            json={"parent": {"database_id": database_id}, "properties": props},
        )
        resp.raise_for_status()
        return resp.json()
    finally:
        if own_client:
            http.close()


def format_iso_date_de(iso_str: str) -> str:
    """Format an ISO date or datetime string as DD.MM.YYYY."""
    date_part = iso_str[:10]
    parsed = date.fromisoformat(date_part)
    return parsed.strftime("%d.%m.%Y")


def parse_notion_temporal(value: str, tz_name: str = "Europe/Vienna") -> date | datetime:
    """Parse a Notion ISO date or datetime string into a date or tz-aware datetime."""
    from zoneinfo import ZoneInfo

    if "T" not in value:
        return date.fromisoformat(value[:10])
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
