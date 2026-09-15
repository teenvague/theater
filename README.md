# Now Playing: Theater

A buildless, single-page theater index. No hero, tagline, footer, secondary pages, accounts or pagination. Typography, thin rules, compact images and text controls follow the agreed MoMA-like direction.

## Run locally

To preview the existing site, use Python 3's built-in HTTP server; no Python packages are needed for this step.

```sh
python3 -m http.server 8000 --directory dist
```

Open http://localhost:8000. Serve over HTTP; double-clicking index.html will not load the JSON feed in browsers that block local-file fetches. Any static host can serve the contents of `dist/`.

To run imports or Python tests, use Python 3.12 (the version used in CI) and install the scraper dependencies:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/requirements.txt
```

Imports also require network access to the configured sources. Node 20 is used by CI for front-end tests.

## Live site and automatic updates

Published at [teenvague.github.io/theater](https://teenvague.github.io/theater/). The public feed contains imported production listings, not demo fixtures.

**Updates are weekly, not continuous or daily.** `.github/workflows/refresh.yml` schedules a refresh on Mondays at 8 a.m. America/New_York. Visitors read the latest published JSON snapshot; opening the site does not run a scraper. Date-based categories can change in the browser without a new import.

Current sources:

| Source | Coverage |
| --- | --- |
| Playbill | Broadway and Off-Broadway indexes, restricted to venues with matching `playbill` aliases in `data/sources.json`. |
| Cherry Lane Theatre | Direct venue adapter, authoritative for its own productions. |
| Manual records | `data/manual.json`, currently used for Armory because its site blocks automated fetching. |

A venue marked `enabled: false` can still be covered by Playbill when it has aliases; that flag disables its own adapter. Venues without aliases or an enabled adapter are not automatically covered. This is a curated index, not a complete inventory of New York productions. A show can be missed if its venue is unrecognized, it is absent from the source indexes, or its start date cannot be verified.

The GitHub refresh workflow collects listings and dates, merges stable production IDs, sources descriptions and artwork, resolves booking links, runs checks, commits the snapshot and publishes it to GitHub Pages. Running `python scripts/refresh.py` locally updates local files only; it does not run tests, commit, push or deploy. TodayTix supplements images and descriptions for already-discovered productions; it does not independently import new productions. Images and descriptions depend on accessible source material and may remain missing. Description and image enrichment failures are logged and do not necessarily fail a refresh.

### Run history and manual refresh

As checked September 15, 2026, recent GitHub refresh runs completed successfully through manual dispatch. A successful scheduled run had not yet been observed. The latest local data refresh at that check was September 15 at about 9:18 a.m. New York time, when Classic Stage Company was added; later passes enriched that snapshot with descriptions, artwork and booking links. These are dated observations, not a continuously updated status report.

For current status, see [Refresh listings and publish runs](https://github.com/teenvague/theater/actions/workflows/refresh.yml), `dist/data/shows.json`, and the health reports in `data/`. To refresh immediately, open that workflow in GitHub Actions and select **Run workflow** on `main`. Manual dispatch bypasses the 8 a.m. gate and publishes after successful collection and checks.

## Features

- Working search, Now Playing / Opening Soon / All, venue filter and reset.
- Responsive production rows with images, credits, venue, neighborhood, date range, text tags and outbound link.
- Production/engagement data model, reference JSON Schema, curated source registry, normalized JSON adapter, runtime validation, ID-based deduplication, atomic feed replacement, per-source health and last-good-data retention. The importer uses its own `validate()` function; it does not execute the JSON Schema.
- Weekly GitHub Actions refresh targeting Monday at 8 AM America/New_York, including daylight saving time, plus manual refresh.

## Files

- `dist/`: entire public front end; `dist/data/shows.json` is its only data dependency.
- `data/sources.json`: curated venue registry, Playbill aliases and adapter configuration.
- `data/production.schema.json`: production and engagement contract.
- `scripts/adapters/json_feed.py`: working reference adapter for normalized HTTPS JSON feeds.
- `scripts/refresh.py`: validation, merge, refresh and source health reporting.
- `.github/workflows/refresh.yml`: weekly import, checks, snapshot commit and deployment.
- `scripts/tickets.py`: official show and booking destinations, stored separately from ingestion URLs.
- `tests/`: calendar/filter and ingestion regression checks.

## Connect live sources

1. Verify a candidate source's actual current website, access terms and robots policy. Prefer a supported feed/API. The source list is editorial planning, not a claim that these venues provide JSON feeds.
2. For a normalized feed, set `url`, `adapter: "json_feed"`, and `enabled: true` in the registry. The endpoint must return `{ "productions": [...] }` using the supplied schema. Engagement sourceId must match the registry id.
3. To cover another venue through Playbill, add its listing-name aliases to `playbill` in the registry; no direct adapter is necessary. For a direct HTML source, write an adapter exposing `fetch(source) -> list[production]`, register its module in the allowlist in `refresh.py`, and add fixture tests. Use the shared network helper for robots checks, request limits and pacing. Playbill records without a usable start date are skipped; Cherry Lane can emit a month-precision start date marked with `startDatePrecision`. There is no separate quarantine queue.
4. Assign stable canonical production IDs and engagement IDs across adapters. A transfer keeps its production ID but gets a new engagement ID. Distinct revivals get distinct production IDs. This deliberately avoids destructive fuzzy title matching. Provide credits, first-performance/opening/closing dates, tags, URLs, image rights and provenance.
5. After installing dependencies, run `python scripts/refresh.py`. Inspect the output and health reports, then run the checks below. Failed sources retain previous live records; if every enabled source fails, the existing feed is left untouched. Empty responses are treated as failures unless `allowEmpty` is explicitly enabled. The manual source permits an empty result, which still counts as a successful source.
6. Push changes to `main`. `.github/workflows/publish.yml` publishes `dist/` to GitHub Pages. The refresh workflow has its own deployment job because bot commits do not retrigger the push workflow.

Missing records are preserved, even after a successful scrape, to protect against partial source responses. Emit `status: "closed"` for explicit closures and maintain closing dates. Open runs remain until explicitly closed. If at least one enabled source succeeds, the importer exits successfully and the workflow can publish the merged feed after checks pass, retaining old records for failed sources. If every enabled source fails, the importer exits with an error and the workflow does not publish. **A green run does not prove every source succeeded**; inspect `data/source-health.json` and the run logs. Per-page failures can also be logged without failing an entire adapter. Sources are fetched sequentially.

On Mondays, the schedule checks both 12:00 and 13:00 UTC, runs only during the New York 8 AM hour, and skips the other invocation. GitHub schedules can be delayed or skipped and are not an exact-time guarantee. A delay past that hour skips the refresh; use manual dispatch if needed.

## Display rules

Artwork is square. Desktop titles align with the image top and descriptions with its bottom; mobile places image and description in the left column and production details in the right. Typography uses Arial with 0.01em tracking. A venue menu uses a keyboard-accessible listbox. Typing in search selects All and clears the venue filter, searching titles, credits, venues and descriptions across current and future productions. The venue filter can then narrow those results. Rows open their official production or booking destination when resolved, with the ingestion URL retained as a fallback.

### Automatic descriptions

When at least one source succeeds, the refresh runs `scripts/summaries.py` independently of artwork. It prefers labeled synopses on production pages, then page description metadata, then TodayTix records verified by title, venue and run dates. It extracts the first eligible sentence rather than generating an AI summary, and preserves that sentence in full. The browser fits desktop text into the space beside the image with a minimum of two lines, truncating overflow; mobile displays the full stored sentence. Source URL and refresh time are stored in the feed. Successful descriptions are cached for seven days; missing descriptions are retried and source failures preserve previous copy. Coverage and failures are recorded in `data/summary-health.json`.

### Booking destinations

`scripts/tickets.py` reads the external **Buy Tickets** link from each Playbill production page and stores it as `ticketUrl`. This can be a venue page, official production website or external ticketing service, not necessarily a direct checkout. Existing direct-source URLs are used as their own booking destinations. Failed lookups retain a previously resolved link; otherwise the row falls back to its ingestion URL. A resolved link is not a guarantee that the destination is reachable or tickets are available.

Now Playing includes first-performance and closing days. Opening Soon includes tomorrow through 30 days ahead. All includes current and future tracked engagements, excluding expired/explicitly closed runs. Default order is closing soonest, open runs last, then newest start date. Opening Soon sorts by first performance. Dates use New York's calendar. No result cap or pagination.

## Check

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/model.test.js
```

Node 20+ is only needed for the front-end tests. The site itself needs no Node runtime, bundler or installation. Data is rendered as text, outbound URLs are restricted to HTTP(S), and new tabs use noopener/noreferrer.

## Listing and artwork corrections (September 2026)

`data/aliases.json` explicitly maps duplicate source IDs to a canonical production and engagement. Shifters' retained Playbill row and Cherry Lane row are the same run. The merge preserves exact dates over month estimates and keeps nonempty credits and artwork while accepting updated metadata. Add aliases only for verified matching engagements; transfers and separate revivals stay distinct.

The Cherry Orchard's confirmed Armory run remains September 16–26, 2026. Now Playing includes the first-performance day; the browser rechecks the New York calendar when returning to a tab and after midnight.

Images are resolved from direct show pages, venue sitemaps/navigation, structured event data, Open Graph/Twitter metadata, and the official ticket/producer link on a Playbill listing. Site-name suffixes are accepted; recognizable generic logos and placeholders are rejected. `data/image-overrides.json` stores verified production-specific pages or artwork when automatic discovery cannot find them. Images that can be downloaded are cached in `dist/images/`; the refresh workflow now commits those files along with their references. Remote fallbacks retain provenance but may still depend on the source CDN's availability. `data/image-health.json` records coverage and remaining gaps; automatic extraction cannot guarantee every future production publishes suitable artwork.

Cached images should be checked visually and used according to the source's applicable image permissions; metadata alone is not a reuse license.

### Automatic images for newly imported productions

Every successful listing refresh calls `images.attach()` before saving the public feed. Existing artwork is reused. New and unresolved records try source artwork, official production/venue pages, and then an automatic TodayTix NYC catalog search. `scripts/artwork_sources.py` loads each catalog index once per run and reads details only for exact title matches. A matching venue (including configured venue aliases) and overlapping run dates are required before the ticketing artwork is accepted. It does not require adding a production-specific URL to the overrides file.

Successful downloads are saved in `dist/images/`, with the original URL, source page and matching method in the image catalog. The existing refresh workflow commits and publishes images alongside listings. `scripts/image_report.py` adds coverage and unresolved titles to the GitHub run summary and fails on dangling local image references. Missing artwork is retried on subsequent refreshes. Source failure does not erase an existing good image.

`data/image-overrides.json` remains an optional exception mechanism, not a required step for each new production. Complete coverage still depends on sources publishing accessible artwork; the resolver leaves a visible missing-image fallback rather than matching a different production. This change keeps the repository's existing weekly refresh schedule.
