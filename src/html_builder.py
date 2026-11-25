"""Generate the interactive German configurator landing page (dist/index.html)."""

from __future__ import annotations

import html
import json
from typing import Any


def build_index_html(
    categories: list[dict[str, Any]],
    events_payload: dict[str, Any],
    worker_base_url: str = "",
) -> str:
    """Render a self-contained static index.html with live filter preview & URL builder."""
    clean_worker = worker_base_url.rstrip("/")
    updated_at = html.escape(events_payload.get("generated_at", ""))
    total_count = len(events_payload.get("events", []))

    static_rows = []
    for cat in categories:
        slug = html.escape(cat["slug"])
        name = html.escape(cat["name"])
        count = int(cat["count"])
        static_rows.append(
            f"""
            <div class="feed-item">
              <div>
                <strong>{name}</strong>
                <span class="badge">{count} Termine</span>
              </div>
              <div class="feed-actions">
                <a class="btn-sm" href="./{slug}.ics">Download .ics</a>
                <button class="btn-sm btn-copy" data-copy-rel="{slug}.ics">URL kopieren</button>
              </div>
            </div>"""
        )
    static_rows_html = "\n".join(static_rows)

    embedded_data = json.dumps(
        {
            "generated_at": events_payload.get("generated_at"),
            "categories": categories,
            "events": events_payload.get("events", []),
            "worker_base_url": clean_worker,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Talente OÖ & MINT Event-Kalender</title>
  <style>
    :root {{
      --bg: #0b1020;
      --surface: #131a2e;
      --surface-2: #1a2340;
      --border: #2a365c;
      --text: #eef2ff;
      --muted: #9aa7c7;
      --accent: #60a5fa;
      --accent-2: #34d399;
      --warn: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{
      max-width: 980px;
      margin: 0 auto;
      padding: 2rem 1.25rem 4rem;
    }}
    h1 {{ margin: 0 0 0.4rem; font-size: 1.9rem; }}
    .sub {{ color: var(--muted); margin: 0 0 1.75rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    h2 {{ margin: 0 0 0.9rem; font-size: 1.2rem; }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    label.field-label {{
      display: block;
      font-size: 0.88rem;
      color: var(--muted);
      margin-bottom: 0.35rem;
    }}
    select, input[type="text"] {{
      width: 100%;
      padding: 0.55rem 0.7rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--surface-2);
      color: var(--text);
      font-size: 0.95rem;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin: 0.6rem 0 1.1rem;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 0.35rem 0.8rem;
      cursor: pointer;
      font-size: 0.88rem;
      user-select: none;
    }}
    .chip input {{ accent-color: var(--accent); }}
    .url-box {{
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-top: 0.6rem;
    }}
    .url-box input {{ flex: 1 1 320px; font-family: ui-monospace, monospace; font-size: 0.84rem; }}
    button, .btn {{
      background: var(--accent);
      color: #061024;
      border: none;
      border-radius: 8px;
      padding: 0.55rem 0.95rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      font-size: 0.9rem;
    }}
    .btn-secondary {{
      background: var(--surface-2);
      color: var(--text);
      border: 1px solid var(--border);
    }}
    .btn-sm {{
      background: var(--surface-2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.3rem 0.65rem;
      font-size: 0.8rem;
      text-decoration: none;
      cursor: pointer;
    }}
    .notice {{
      margin-top: 0.6rem;
      font-size: 0.85rem;
      color: var(--warn);
    }}
    .preview-list {{
      max-height: 360px;
      overflow-y: auto;
      display: grid;
      gap: 0.55rem;
      margin-top: 0.75rem;
    }}
    .ev-row {{
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.65rem 0.85rem;
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .ev-meta {{ color: var(--muted); font-size: 0.83rem; }}
    .feed-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }}
    .feed-item:last-child {{ border-bottom: none; }}
    .feed-actions {{ display: flex; gap: 0.4rem; }}
    .badge {{
      display: inline-block;
      margin-left: 0.4rem;
      padding: 0.1rem 0.45rem;
      border-radius: 999px;
      background: var(--surface-2);
      color: var(--muted);
      font-size: 0.75rem;
    }}
    ol {{ margin: 0.4rem 0 0; padding-left: 1.25rem; color: var(--muted); }}
    li strong {{ color: var(--text); }}
    .muted {{ color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Talente OÖ &amp; MINT Event-Kalender</h1>
    <p class="sub">Kuratierter Kalender für Talente OÖ, Olympiaden und MINT-Events. Letzter Sync: {updated_at} ({total_count} Live-Einträge)</p>

    <section class="card">
      <h2>1. Persönlichen Kalender konfigurieren</h2>
      <div class="grid-2">
        <div>
          <label class="field-label" for="gradeSelect">Schulstufe</label>
          <select id="gradeSelect">
            <option value="">Alle Schulstufen (3.-13.)</option>
            <option value="3">3. Schulstufe (VS)</option>
            <option value="4">4. Schulstufe (VS)</option>
            <option value="5">5. Schulstufe (1. Kl. AHS/MS)</option>
            <option value="6">6. Schulstufe (2. Kl. AHS/MS)</option>
            <option value="7">7. Schulstufe (3. Kl. AHS/MS)</option>
            <option value="8">8. Schulstufe (4. Kl. AHS/MS)</option>
            <option value="9">9. Schulstufe (5. Kl. / 1. HTL)</option>
            <option value="10">10. Schulstufe (6. Kl. / 2. HTL)</option>
            <option value="11">11. Schulstufe (7. Kl. / 3. HTL)</option>
            <option value="12">12. Schulstufe (8. Kl. / 4. HTL)</option>
            <option value="13">13. Schulstufe (5. HTL)</option>
          </select>
        </div>
        <div>
          <label class="field-label" for="deadlineSelect">Anmeldefristen</label>
          <select id="deadlineSelect">
            <option value="1">Termine + eigene [FRIST]-Events</option>
            <option value="0">Nur Termine (Frist steht in Beschreibung)</option>
            <option value="only">Nur [FRIST]-Events</option>
          </select>
        </div>
      </div>

      <label class="field-label">Interessen / Kategorien (keine Auswahl = alle)</label>
      <div id="categoryChips" class="chips"></div>

      <label class="field-label" for="feedUrl">Deine persönliche Abo-URL (.ics)</label>
      <div class="url-box">
        <input id="feedUrl" type="text" readonly />
        <button id="copyBtn" type="button">URL kopieren</button>
        <a id="webcalBtn" class="btn btn-secondary" href="#">Apple / Outlook</a>
        <a id="gcalBtn" class="btn btn-secondary" target="_blank" rel="noopener" href="#">Google Calendar</a>
      </div>
      <div id="workerNotice" class="notice" hidden></div>
    </section>

    <section class="card">
      <h2>2. Vorschau (<span id="previewCount">0</span> passende Termine)</h2>
      <div id="previewList" class="preview-list"></div>
    </section>

    <section class="card">
      <h2>3. So abonnierst du den Kalender (aktualisiert sich automatisch)</h2>
      <ol>
        <li><strong>Google Calendar (Web):</strong> Linke Leiste bei „Weitere Kalender“ auf <strong>+</strong> → „Per URL“ → kopierte URL einfügen.</li>
        <li><strong>Apple Calendar (iPhone / Mac):</strong> Auf „Apple / Outlook“ tippen oder Ablage → „Neues Kalenderabonnement“.</li>
        <li><strong>Outlook:</strong> Kalender hinzufügen → „Aus dem Web abonnieren“ → URL einfügen.</li>
      </ol>
    </section>

    <section class="card">
      <h2>4. Direkte statische Feeds (ohne Filter)</h2>
      <div class="feed-item">
        <div><strong>Alle Termine</strong><span class="badge">{total_count}</span></div>
        <div class="feed-actions">
          <a class="btn-sm" href="./all.ics">Download .ics</a>
          <button class="btn-sm btn-copy" data-copy-rel="all.ics">URL kopieren</button>
        </div>
      </div>
      <div class="feed-item">
        <div><strong>Alle Termine + Fristen</strong></div>
        <div class="feed-actions">
          <a class="btn-sm" href="./all-mit-fristen.ics">Download .ics</a>
          <button class="btn-sm btn-copy" data-copy-rel="all-mit-fristen.ics">URL kopieren</button>
        </div>
      </div>
      <div class="feed-item">
        <div><strong>Nur Anmeldefristen ([FRIST])</strong></div>
        <div class="feed-actions">
          <a class="btn-sm" href="./fristen.ics">Download .ics</a>
          <button class="btn-sm btn-copy" data-copy-rel="fristen.ics">URL kopieren</button>
        </div>
      </div>
      {static_rows_html}
    </section>
  </div>

  <script id="calendar-data" type="application/json">{embedded_data}</script>
  <script>
    const DATA = JSON.parse(document.getElementById("calendar-data").textContent);
    const gradeSelect = document.getElementById("gradeSelect");
    const deadlineSelect = document.getElementById("deadlineSelect");
    const chipsWrap = document.getElementById("categoryChips");
    const feedUrlInput = document.getElementById("feedUrl");
    const copyBtn = document.getElementById("copyBtn");
    const webcalBtn = document.getElementById("webcalBtn");
    const gcalBtn = document.getElementById("gcalBtn");
    const workerNotice = document.getElementById("workerNotice");
    const previewCount = document.getElementById("previewCount");
    const previewList = document.getElementById("previewList");

    const selectedCats = new Set();

    for (const cat of DATA.categories) {{
      const label = document.createElement("label");
      label.className = "chip";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = cat.slug;
      cb.addEventListener("change", () => {{
        if (cb.checked) selectedCats.add(cat.slug);
        else selectedCats.delete(cat.slug);
        update();
      }});
      label.appendChild(cb);
      label.appendChild(document.createTextNode(`${{cat.name}} (${{cat.count}})`));
      chipsWrap.appendChild(label);
    }}

    function matches(ev, grade, cats) {{
      if (grade !== null) {{
        if (ev.grade_min !== null && grade < ev.grade_min) return false;
        if (ev.grade_max !== null && grade > ev.grade_max) return false;
      }}
      if (cats.size > 0) {{
        const evSlugs = ev.category_slugs || [];
        if (!evSlugs.some((s) => cats.has(s))) return false;
      }}
      return true;
    }}

    function buildUrl(grade, cats, deadlines) {{
      const pageBase = new URL(".", window.location.href).href.replace(/\\/$/, "");
      if (!DATA.worker_base_url) {{
        workerNotice.hidden = false;
        workerNotice.textContent = "Hinweis: Personalisierte Filter-URLs benötigen den Cloudflare Worker (WORKER_BASE_URL). Solange dieser nicht gesetzt ist, wird der passende statische Feed verwendet.";
        if (deadlines === "only" && grade === null && cats.size === 0) return `${{pageBase}}/fristen.ics`;
        if (cats.size === 1 && grade === null && deadlines === "0") {{
          return `${{pageBase}}/${{[...cats][0]}}.ics`;
        }}
        return deadlines === "1" ? `${{pageBase}}/all-mit-fristen.ics` : `${{pageBase}}/all.ics`;
      }}
      workerNotice.hidden = true;
      const url = new URL(`${{DATA.worker_base_url}}/feed.ics`);
      if (grade !== null) url.searchParams.set("grade", String(grade));
      if (cats.size > 0) url.searchParams.set("cats", [...cats].join(","));
      if (deadlines !== "0") url.searchParams.set("deadlines", deadlines);
      return url.toString();
    }}

    function update() {{
      const grade = gradeSelect.value ? Number(gradeSelect.value) : null;
      const deadlines = deadlineSelect.value;
      const url = buildUrl(grade, selectedCats, deadlines);
      feedUrlInput.value = url;
      webcalBtn.href = url.replace(/^https?:\\/\\//, "webcal://");
      gcalBtn.href = `https://calendar.google.com/calendar/r?cid=${{encodeURIComponent(url)}}`;

      const filtered = DATA.events.filter((ev) => matches(ev, grade, selectedCats));
      previewCount.textContent = String(filtered.length);
      previewList.innerHTML = "";
      for (const ev of filtered.slice(0, 60)) {{
        const row = document.createElement("div");
        row.className = "ev-row";
        const left = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = ev.status === "Cancelled" ? `[ABGESAGT] ${{ev.name}}` : ev.name;
        const meta = document.createElement("div");
        meta.className = "ev-meta";
        const parts = [ev.datum_start.slice(0, 10)];
        if (ev.location) parts.push(ev.location);
        if (ev.grade_min !== null && ev.grade_max !== null) parts.push(`${{ev.grade_min}}.-${{ev.grade_max}}. Sst.`);
        if (ev.deadline) parts.push(`Frist: ${{ev.deadline}}`);
        meta.textContent = parts.join(" · ");
        left.appendChild(title);
        left.appendChild(meta);
        row.appendChild(left);
        if (ev.link) {{
          const a = document.createElement("a");
          a.className = "btn-sm";
          a.href = ev.link;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = "Infos";
          row.appendChild(a);
        }}
        previewList.appendChild(row);
      }}
    }}

    copyBtn.addEventListener("click", async () => {{
      await navigator.clipboard.writeText(feedUrlInput.value);
      copyBtn.textContent = "Kopiert!";
      setTimeout(() => (copyBtn.textContent = "URL kopieren"), 1500);
    }});

    document.querySelectorAll(".btn-copy").forEach((btn) => {{
      btn.addEventListener("click", async () => {{
        const abs = new URL(btn.dataset.copyRel, window.location.href).href;
        await navigator.clipboard.writeText(abs);
        btn.textContent = "Kopiert!";
        setTimeout(() => (btn.textContent = "URL kopieren"), 1500);
      }});
    }});

    gradeSelect.addEventListener("change", update);
    deadlineSelect.addEventListener("change", update);
    update();
  </script>
</body>
</html>
"""
