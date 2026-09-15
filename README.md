# Now Playing: Theater

A buildless, single-page theater index. No hero, tagline, footer, secondary pages, accounts or pagination. Typography, thin rules, compact images and text controls follow the agreed MoMA-like direction.

## Run locally

Requires Python 3.9+; no packages to install.

```sh
python3 -m http.server 8000 --directory dist
```

Open http://localhost:8000. Serve over HTTP; double-clicking index.html will not load the JSON feed in browsers that block local-file fetches. Any static host can serve the contents of `dist/`.

## Included / readiness

- Working search, Now Playing / Opening Soon / All, venue/type filters and reset.
- Responsive production rows with images, credits, venue, neighborhood, date range, text tags and outbound link.
- Production/engagement data model, JSON Schema, curated source registry, normalized JSON adapter, validation, ID-based deduplication, atomic feed replacement, per-source health and last-good-data retention.
- Daily GitHub Actions scaffold targeting 8 AM America/New_York, including daylight saving time, plus manual refresh.
- No site has been published and no scheduled job is active until installed in your GitHub repository.

**The bundled records are demo fixtures, not verified current listings.** They reproduce the examples and illustrative dates from the design discussion. Demo mode fixes the browsing date at September 14, 2026 so the preview remains populated. A small in-page label identifies this. Stock images are remote Unsplash URLs from that discussion, not production photos; network access is needed and failed images display a text fallback. Links go to institution homepages for demonstration, not verified ticket pages. Replace these with verified production URLs and authorized images in live feeds.

## Files

- `dist/`: entire public front end; `dist/data/shows.json` is its only data dependency.
- `data/sources.json`: 40 candidate venues/presenters, prioritized from the discussion, disabled by default.
- `data/production.schema.json`: production and engagement contract.
- `scripts/adapters/json_feed.py`: working reference adapter for normalized HTTPS JSON feeds.
- `scripts/refresh.py`: validation, merge, refresh and source health reporting.
- `.github/workflows/refresh.yml`: daily refresh scaffold.
- `tests/`: calendar/filter and ingestion regression checks.

## Connect live sources

1. Verify a candidate source's actual current website, access terms and robots policy. Prefer a supported feed/API. The source list is editorial planning, not a claim that these venues provide JSON feeds.
2. For a normalized feed, set `url`, `adapter: "json_feed"`, and `enabled: true` in the registry. The endpoint must return `{ "productions": [...] }` using the supplied schema. Engagement sourceId must match the registry id.
3. For HTML, write a venue-specific adapter exposing `fetch(source) -> list[production]`, register its module in the adapter allowlist in `refresh.py`, and add saved HTML fixture tests. No unverified venue selectors are shipped. Include bounded requests, timeouts, respectful delays and source-specific parsing. If dates are missing or ambiguous, quarantine the record for review instead of guessing.
4. Assign stable canonical production IDs and engagement IDs across adapters. A transfer keeps its production ID but gets a new engagement ID. Distinct revivals get distinct production IDs. This deliberately avoids destructive fuzzy title matching. Provide credits, first-performance/opening/closing dates, tags, URLs, image rights and provenance.
5. Run `python3 scripts/refresh.py`. On the first successful live refresh, demo fixtures are replaced and demo mode is removed. Failed sources retain previous live records; a total failure leaves the published feed byte-for-byte intact. Empty responses are treated as failures unless `allowEmpty` is explicitly enabled.
6. Push this project to a GitHub repository with Actions and workflow write permission enabled. Its default branch must contain the workflow. Configure your static host to publish `dist/` after feed commits (or add a deployment step using your host's credentials). This package does not provision hosting. Some hosting workflows do not trigger from bot commits; use an explicit deployment step in that case.

Missing records are preserved, even after a successful scrape, to protect against partial source responses. Emit `status: "closed"` for explicit closures and maintain closing dates. Open runs remain until explicitly closed. Review `data/source-health.json` after refresh failures; GitHub marks partial or total source failures red while retaining successful source updates. Sources are fetched sequentially. For a larger registry, add source-specific rate limits and retry/backoff policies before scaling.

The schedule checks both 12:00 and 13:00 UTC, runs only during the New York 8 AM hour, and skips the other invocation. GitHub schedules can be delayed or skipped and are not an exact-time guarantee. A delay past that hour skips the refresh; use manual dispatch or a dedicated scheduler if strict timing is required.

## Display rules

Desktop artwork uses a 3:2 landscape crop. A venue menu uses a keyboard-accessible listbox styled with the site's typography and rules. Typing in search selects All and clears the venue filter, searching titles, credits, venues and descriptions across current and future productions. Filters can then narrow those results.

### Automatic one-line descriptions

Each successful refresh runs `scripts/summaries.py` independently of artwork. It prefers labeled synopses on production pages, then page description metadata, then TodayTix records verified by title, venue and run dates. Complete summary sentences are preserved; the browser truncates only when they exceed the available desktop space, with source URL and refresh time stored in the feed. Successful descriptions are cached for seven days; missing descriptions are retried and source failures preserve previous copy. Coverage and failures are recorded in `data/summary-health.json`. The existing weekly workflow publishes these descriptions with the listings.

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
