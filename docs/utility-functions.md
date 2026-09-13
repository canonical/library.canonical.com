# Utility Functions

This document covers the general-purpose helper functions defined in `webapp/app.py` and the small utilities under `webapp/utils/`.

---

## Application-level Utilities (`webapp/app.py`)

### `get_google_drive_instance()`

Returns a per-request singleton `GoogleDrive` instance stored in Flask's `g` object.

- Creates a new instance on first call within a request context.
- Subsequent calls within the same request reuse `g.google_drive`.

---

### `get_list_of_urls()`

Fetches the URL redirect mapping from the Google Spreadsheet identified by `URL_FILE` (env var) and stores it in `g.list_of_urls`.

Each row is parsed as a CSV pair:

```
old_path,new_path
```

The result is a list of `{"old": ..., "new": ...}` dicts.

---

### `find_broken_url(url)`

Looks up a given URL path in the redirect list. Calls `get_list_of_urls()` on first use if the list is not yet in `g`.

Returns the redirect target as a string, or `None` if no mapping exists.

---

### `assets_ready() → bool`

Returns `True` when both of the following are present on disk:

- `static/css/styles.css`
- At least one hashed CSS bundle matching `static/css/index-*.css`

Used to prevent caching pages that reference missing CSS bundles during first boot. Cache warming and the `check_status_cache` job are skipped while this returns `False`.

---

### `redis_healthy() → bool`

Returns `True` if the Redis cache backend is reachable. Currently a lightweight check that inspects the `cache.cache` attribute and returns `True` unless an exception is raised.

Used by the `@cache.cached` decorator's `unless` callback to bypass caching when Redis is unavailable.

---

### `inject_assets()` (context processor)

Registered via `@app.context_processor`. Injects `hashed_css_path` into every template context.

- Scans `static/css/` for files matching `index-*.css`.
- Returns the relative path to the most recently modified match.
- Returns `{"hashed_css_path": None}` if no match is found.

---

### `_requests_session_with_env_ca(raw)`

Builds a `requests.Session` that uses a custom CA certificate for HTTPS connections. Accepts the certificate as:

- A multi-line PEM string.
- A single-line PEM string with literal `\n` separators.
- A base64-encoded PEM or DER certificate.

Returns a `requests.Session` mounted with an `SSLContextAdapter`, or `None` if `raw` is falsy.

Used by OpenSearch routes when `OPENSEARCH_TLS_CA` is set.

---

### `_ensure_highlight_limit(index_name, limit=5_000_000)`

Calls the OpenSearch `PUT /{index}/_settings` API to raise `index.highlight.max_analyzed_offset` to the given limit.

Called automatically by the search route when a query returns an HTTP 400 error referencing `max_analyzed_offset`.

---

### `warm_single_url(url, navigation_data)`

Warms the cache for a single URL by creating a test request context and calling the `document()` view function directly.

- Creates a deep copy of `navigation_data` to avoid cross-thread state mutation.
- Errors are caught and printed without interrupting the warm-up loop.

---

### `warm_cache_for_urls(urls)`

Warms the cache for a list of URLs using a `ThreadPoolExecutor` (8 workers). Calls `warm_single_url` for each URL.

- Skips silently if `assets_ready()` returns `False`.
- Constructs fresh navigation data once and shares it across workers via deep copies.

---

### `get_urls_expiring_soon()`

Reads all URLs from `static/assets/url_list.txt` and returns them as a list of `{"url": ...}` dicts.

When Redis is configured, all URLs are considered "expiring" (i.e., candidates for cache warming). When only simple cache is used, returns an empty list with a log message.

---

### `db_can_write() → bool`

Executes `SHOW transaction_read_only` against the PostgreSQL connection. Returns `True` if the database is writable. Used during startup to skip `create_all()` on read-only replicas.

---

## `webapp/utils/` Modules

### `make_snippet.render_snippet(highlight, full_html, query)`

Located in `webapp/utils/make_snippet.py`.

Generates a short text snippet for search result cards.

- Prefers the OpenSearch highlight fragment (`highlight`) when available.
- Falls back to extracting a relevant passage from `full_html` based on `query`.
- Returns a plain-text or lightly marked-up string suitable for display.

---

### `process_leading_number` — `extract_leading_number` / `remove_leading_number`

Located in `webapp/utils/process_leading_number.py`.

Helpers used by `NavigationBuilder` to handle numeric prefixes on Google Drive folder/file names (e.g. `"01-Introduction"`).

- `extract_leading_number(name)` — Returns the leading integer or `None`.
- `remove_leading_number(name)` — Strips the numeric prefix and returns the clean name.

These are used to sort navigation items by position before falling back to alphabetical order.

---

### `entity_to_char`

Located in `webapp/utils/entity_to_char.py`.

Converts HTML entities to their character equivalents. Used by the parser when cleaning up exported Google Docs HTML.
