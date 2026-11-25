const VIENNA_TZ = "Europe/Vienna";
const UID_DOMAIN = "talente-ooe-cal";

const VTIMEZONE_VIENNA = [
  "BEGIN:VTIMEZONE",
  "TZID:Europe/Vienna",
  "BEGIN:STANDARD",
  "DTSTART:19701025T030000",
  "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
  "TZOFFSETFROM:+0200",
  "TZOFFSETTO:+0100",
  "TZNAME:CET",
  "END:STANDARD",
  "BEGIN:DAYLIGHT",
  "DTSTART:19700329T020000",
  "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
  "TZOFFSETFROM:+0100",
  "TZOFFSETTO:+0200",
  "TZNAME:CEST",
  "END:DAYLIGHT",
  "END:VTIMEZONE",
];

function escapeIcsText(value) {
  return String(value ?? "")
    .replace(/\\/g, "\\\\")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\n/g, "\\n")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,");
}

function foldLine(line) {
  const encoder = new TextEncoder();
  if (encoder.encode(line).length <= 75) return line;
  const chunks = [];
  let current = "";
  let currentBytes = 0;
  let limit = 75;
  for (const ch of line) {
    const b = encoder.encode(ch).length;
    if (currentBytes + b > limit) {
      chunks.push(current);
      current = " " + ch;
      currentBytes = 1 + b;
      limit = 75;
    } else {
      current += ch;
      currentBytes += b;
    }
  }
  if (current) chunks.push(current);
  return chunks.join("\r\n");
}

function formatUtcStamp(date) {
  const iso = date.toISOString().replace(/[-:]/g, "");
  return iso.slice(0, 15) + "Z";
}

function toViennaLocalIcs(isoStr) {
  const d = new Date(isoStr);
  const fmt = new Intl.DateTimeFormat("sv-SE", {
    timeZone: VIENNA_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const parts = Object.fromEntries(fmt.formatToParts(d).map((p) => [p.type, p.value]));
  const hh = parts.hour === "24" ? "00" : parts.hour;
  return `${parts.year}${parts.month}${parts.day}T${hh}${parts.minute}${parts.second}`;
}

function addDaysToIsoDate(isoDateStr, days) {
  const [y, m, d] = isoDateStr.slice(0, 10).split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return dt.toISOString().slice(0, 10).replace(/-/g, "");
}

function formatDateDe(isoStr) {
  const [y, m, d] = isoStr.slice(0, 10).split("-");
  return `${d}.${m}.${y}`;
}

function buildDescription(ev) {
  const lines = [];
  if (ev.deadline) lines.push(`Anmeldeschluss: ${formatDateDe(ev.deadline)}`);
  if (ev.grade_min !== null && ev.grade_min !== undefined && ev.grade_max !== null && ev.grade_max !== undefined) {
    lines.push(`Schulstufe: ${ev.grade_min}.-${ev.grade_max}. Schulstufe`);
  }
  if (ev.cost) lines.push(`Kosten: ${ev.cost}`);
  if (ev.organizer) lines.push(`Veranstalter: ${ev.organizer}`);
  if (Array.isArray(ev.categories) && ev.categories.length) {
    lines.push(`Kategorien: ${ev.categories.join(", ")}`);
  }
  if (ev.description) {
    if (lines.length) lines.push("");
    lines.push(ev.description);
  }
  if (ev.link) {
    if (lines.length) lines.push("");
    lines.push(`Infos & Anmeldung: ${ev.link}`);
  }
  return lines.join("\n").trim();
}

export function matchesFilters(ev, gradeParam, catSlugsSet) {
  if (gradeParam !== null && !Number.isNaN(gradeParam)) {
    if (ev.grade_min !== null && ev.grade_min !== undefined && gradeParam < ev.grade_min) return false;
    if (ev.grade_max !== null && ev.grade_max !== undefined && gradeParam > ev.grade_max) return false;
  }
  if (catSlugsSet.size > 0) {
    const slugs = ev.category_slugs || [];
    if (!slugs.some((s) => catSlugsSet.has(s))) return false;
  }
  return true;
}

export function generateIcsFromEvents(eventsData, searchParams, nowDate = new Date()) {
  const gradeRaw = searchParams.get("grade");
  const grade = gradeRaw !== null && gradeRaw !== "" ? Number(gradeRaw) : null;
  const catsRaw = searchParams.get("cats") || "";
  const catSlugsSet = new Set(
    catsRaw
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
  );
  const deadlinesMode = (searchParams.get("deadlines") || "0").toLowerCase();
  const includeDeadlines = deadlinesMode === "1" || deadlinesMode === "true";
  const deadlinesOnly = deadlinesMode === "only";

  const filtered = (eventsData.events || []).filter((ev) => matchesFilters(ev, grade, catSlugsSet));
  const dtstamp = formatUtcStamp(nowDate);

  const calTitleParts = ["Talente OÖ & MINT"];
  if (grade !== null && !Number.isNaN(grade)) calTitleParts.push(`${grade}. Sst.`);
  if (deadlinesOnly) calTitleParts.push("Fristen");

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Talente OOE Community//Personal Event Calendar//DE",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${escapeIcsText(calTitleParts.join(" - "))}`,
    `X-WR-TIMEZONE:${VIENNA_TZ}`,
    "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    "X-PUBLISHED-TTL:PT12H",
    ...VTIMEZONE_VIENNA,
  ];

  for (const ev of filtered) {
    const isCancelled = (ev.status || "").toLowerCase() === "cancelled";
    const lastMod = ev.last_edited_time ? formatUtcStamp(new Date(ev.last_edited_time)) : dtstamp;

    if (!deadlinesOnly) {
      lines.push("BEGIN:VEVENT");
      lines.push(`UID:${ev.page_id}@${UID_DOMAIN}`);
      lines.push(`DTSTAMP:${dtstamp}`);
      lines.push(`LAST-MODIFIED:${lastMod}`);
      lines.push(`SUMMARY:${escapeIcsText(isCancelled ? `[ABGESAGT] ${ev.name}` : ev.name)}`);
      lines.push(`STATUS:${isCancelled ? "CANCELLED" : "CONFIRMED"}`);

      if (ev.datum_start && ev.datum_start.includes("T")) {
        lines.push(`DTSTART;TZID=${VIENNA_TZ}:${toViennaLocalIcs(ev.datum_start)}`);
        let endIso = ev.datum_end;
        if (!endIso) {
          endIso = new Date(new Date(ev.datum_start).getTime() + 2 * 3600 * 1000).toISOString();
        } else if (!endIso.includes("T")) {
          endIso = `${endIso.slice(0, 10)}T23:59:00`;
        }
        lines.push(`DTEND;TZID=${VIENNA_TZ}:${toViennaLocalIcs(endIso)}`);
      } else if (ev.datum_start) {
        lines.push(`DTSTART;VALUE=DATE:${ev.datum_start.slice(0, 10).replace(/-/g, "")}`);
        const endBase = ev.datum_end && ev.datum_end.slice(0, 10) >= ev.datum_start.slice(0, 10)
          ? ev.datum_end
          : ev.datum_start;
        lines.push(`DTEND;VALUE=DATE:${addDaysToIsoDate(endBase, 1)}`);
      }

      if (ev.location) lines.push(`LOCATION:${escapeIcsText(ev.location)}`);
      const desc = buildDescription(ev);
      if (desc) lines.push(`DESCRIPTION:${escapeIcsText(desc)}`);
      if (ev.link) lines.push(`URL:${ev.link}`);
      if (Array.isArray(ev.categories) && ev.categories.length) {
        lines.push(`CATEGORIES:${ev.categories.map(escapeIcsText).join(",")}`);
      }
      lines.push("END:VEVENT");
    }

    if ((includeDeadlines || deadlinesOnly) && ev.deadline && ev.create_deadline_event) {
      const d = ev.deadline.slice(0, 10);
      lines.push("BEGIN:VEVENT");
      lines.push(`UID:${ev.page_id}-deadline@${UID_DOMAIN}`);
      lines.push(`DTSTAMP:${dtstamp}`);
      lines.push(`LAST-MODIFIED:${lastMod}`);
      lines.push(`SUMMARY:${escapeIcsText(isCancelled ? `[ABGESAGT] [FRIST] ${ev.name}` : `[FRIST] ${ev.name}`)}`);
      lines.push(`STATUS:${isCancelled ? "CANCELLED" : "CONFIRMED"}`);
      lines.push(`DTSTART;VALUE=DATE:${d.replace(/-/g, "")}`);
      lines.push(`DTEND;VALUE=DATE:${addDaysToIsoDate(d, 1)}`);
      const dlDesc = [
        `Anmeldeschluss für: ${ev.name}`,
        `Veranstaltungstermin: ${formatDateDe(ev.datum_start)}`,
        ev.organizer ? `Veranstalter: ${ev.organizer}` : "",
        ev.link ? `Anmeldung: ${ev.link}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      lines.push(`DESCRIPTION:${escapeIcsText(dlDesc)}`);
      if (ev.link) lines.push(`URL:${ev.link}`);
      lines.push("END:VEVENT");
    }
  }

  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}

export function parseParamsFromUrl(url) {
  const m = url.pathname.match(/^\/cal\/g([^/]+)\/d([^/]+)\/([^/]+)\.ics$/i);
  if (m) {
    const params = new URLSearchParams();
    if (m[1].toLowerCase() !== "all") params.set("grade", m[1]);
    params.set("deadlines", m[2].toLowerCase());
    if (m[3].toLowerCase() !== "all") {
      params.set("cats", decodeURIComponent(m[3]).replace(/\+/g, ","));
    }
    return params;
  }
  return url.searchParams;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return new Response("ok", { status: 200 });
    }
    const headers = {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": 'inline; filename="talente-ooe-personal.ics"',
      "Cache-Control": "public, max-age=900",
      "Access-Control-Allow-Origin": "*",
    };
    if (request.method === "HEAD") {
      return new Response(null, { status: 200, headers });
    }
    if (!env.EVENTS_JSON_URL) {
      return new Response("Missing EVENTS_JSON_URL env var", { status: 500 });
    }
    const upstream = await fetch(env.EVENTS_JSON_URL, {
      cf: { cacheEverything: true, cacheTtl: 900 },
    });
    if (!upstream.ok) {
      return new Response(`Upstream error: ${upstream.status}`, { status: 502 });
    }
    const eventsData = await upstream.json();
    const params = parseParamsFromUrl(url);
    const icsBody = generateIcsFromEvents(eventsData, params);
    return new Response(icsBody, {
      status: 200,
      headers,
    });
  },
};
