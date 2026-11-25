# Talente OÖ & MINT Event-Kalender

Automated, Notion-backed calendar system for curated STEM, Olympiad, and **Talente OÖ** events.

- **Single Source of Truth:** Notion database (`📅 Talente-OÖ Event-Kalender`)
- **Build & Static Feeds:** GitHub Actions (every 3h + manual trigger) -> GitHub Pages (`events.json`, `all.ics`, `fristen.ics`, `<kategorie>.ics`, `index.html`)
- **Personalized Feeds:** Free Cloudflare Worker filtering `events.json` by exact grade (`Schulstufe`), categories, and deadline preference (`?grade=10&cats=talente-ooe,olympiade-mathe&deadlines=1`)

---

## Handover & Setup Guide (< 15 Minutes)

### 1. Notion Integration & Database Sharing
1. Open [notion.so/my-integrations](https://www.notion.so/my-integrations) -> **New integration** -> name it `Talente-Kalender-Sync` -> select the workspace -> copy the **Internal Integration Secret** (`ntn_...` / `secret_...`).
2. Open the **`📅 Talente-OÖ Event-Kalender`** database in Notion -> top-right **`•••`** menu -> **Connections** -> add `Talente-Kalender-Sync` (read-only access is enough for syncing; read+write if using `scripts/ingest_drafts.py`).
3. Copy the **Database ID** from the Notion database URL (`https://www.notion.so/<workspace>/<DATABASE_ID>?v=...` -> the 32-character hex string before `?v=`).

### 2. GitHub Secrets & Pages
In your GitHub repo **Settings -> Secrets and variables -> Actions**:
- Add **Secrets**:
  - `NOTION_TOKEN`: your Notion integration secret
  - `NOTION_DATABASE_ID`: the 32-char database ID
- Enable **GitHub Pages**: **Settings -> Pages -> Source: GitHub Actions**.
- Run **Actions -> Sync Notion Calendar to GitHub Pages -> Run workflow** once manually.

### 3. Cloudflare Worker (for personalized filter URLs)
1. Install Wrangler or use `npx wrangler`:
   ```bash
   cd worker
   npx wrangler login
   npx wrangler deploy
   ```
2. Copy the deployed Worker URL (e.g. `https://talente-ooe-calendar-worker.<user>.workers.dev`).
3. In GitHub **Settings -> Secrets and variables -> Actions -> Variables**, add:
   - `WORKER_BASE_URL`: your deployed Worker URL (no trailing slash)
4. Re-run the GitHub Action so `index.html` points to your live Worker.

---

## Maintaining Events in Notion (Rules)

> **Warning:** Do **not** rename the Notion columns (`Name`, `Datum`, `Anmeldefrist`, `Frist-Event`, `Status`, `Kategorie`, `Schulstufe von`, `Schulstufe bis`, `Veranstalter`, `Ort`, `Kosten`, `Link`, `Beschreibung`) without updating `src/notion_client.py`. Adding new `Kategorie` tags in Notion is safe and automatically creates a new `.ics` feed and checkbox on the website.

- **`Status`:**
  - `Draft`: ignored (staging area for AI agents / unverified entries)
  - `Live`: published to all matching feeds
  - `Cancelled`: kept in feeds as `[ABGESAGT] ...` with `STATUS:CANCELLED`
  - `Archived`: removed from feeds
- **Long Course Series (> 7 days, e.g. Regionalakademie, JKU Mathe-Treff):** Put only the **first session** in `Datum` and note `(Kursreihe bis DD.MM.YYYY)` in `Beschreibung`, otherwise calendar clients show a multi-month banner.
- **Deadlines:** Filling `Anmeldefrist` + checking `Frist-Event` creates a toggleable `[FRIST]` all-day event in addition to showing the deadline at the top of the event description.

---

## AI Agent Ingest Workflow (`scripts/ingest_drafts.py`)

Agents can extract unstructured PDFs, emails, or web pages into a JSON array and insert deduplicated `Draft` rows directly:

```json
[
  {
    "name": "ÖMO Regionalwettbewerb",
    "datum_start": "2027-03-31T09:00:00+02:00",
    "datum_end": "2027-04-02T12:00:00+02:00",
    "deadline": "2027-03-10",
    "categories": ["Olympiade: Mathe"],
    "grade_min": 9,
    "grade_max": 13,
    "organizer": "ÖMO",
    "location": "Wels",
    "cost": "0,00 €",
    "link": "https://www.oemo.at/",
    "description": "Regionalwettbewerb für Fortgeschrittene."
  }
]
```

Run:
```bash
python scripts/ingest_drafts.py events.json --dry-run
python scripts/ingest_drafts.py events.json
```
