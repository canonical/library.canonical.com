# Search

Search is handled by the `GET /search` route in `webapp/app.py`. It uses **OpenSearch** as the primary backend and falls back to a direct **Google Drive** full-text search when OpenSearch is not configured or returns an error.

---

## Flow Overview

```
GET /search?q=<query>
        │
        ▼
OpenSearch configured?
    Yes ─────► Query OpenSearch ──► results
    No  ─────► Google Drive search ──► results
        │                               │
        └──────── render search.html ◄──┘
```

---

## OpenSearch Query

When `OPENSEARCH_URL`, `OPENSEARCH_USERNAME`, and `OPENSEARCH_PASSWORD` are all set, the route sends a `POST /{index}/_search` request.

### Popularity Scoring

Results are boosted by page popularity using a `function_score` query:

```
final_score = text_relevance_score + popularity_weight * log(1 + views)
```

- `popularity_weight` is read from `OPENSEARCH_POPULARITY_WEIGHT` (default `0.001`).
- Set `OPENSEARCH_POPULARITY_WEIGHT=0` to disable popularity scoring entirely and use a plain `query_string` query.

### Highlighting

When a non-empty query string is provided, the `full_html` field is highlighted using the `unified` highlighter:

- Fragment size: 300 characters
- 1 fragment per document
- Boundary scanner: `sentence` (locale `en-US`)
- Matched terms are wrapped in `<strong>…</strong>`.

If a `max_analyzed_offset` error is returned (HTTP 400), the route automatically raises the limit to 5 000 000 via `_ensure_highlight_limit` and retries the query once.

### Sorting

- With a query string: results are ranked by relevance + popularity score.
- Without a query string (`q` is empty): results are sorted by `_id` descending.

### Result Shape

Each hit is mapped to:

| Field         | Source                                          |
|---------------|-------------------------------------------------|
| `id`          | OpenSearch `_id` (Google Drive file ID)        |
| `full_path`   | `_source.path`                                  |
| `breadcrumbs` | Path segments excluding the last component     |
| `name`        | `doc_metadata.title` or path fallback          |
| `owner`       | `_source.owner`                                 |
| `type`        | `doc_metadata.type`                             |
| `description` | Highlighted snippet or snippet from `full_html` |

### Filtered Results

Documents whose path contains `/tests-and-issues-(for-development-purpose)` are removed from the results before rendering.

---

## Google Drive Fallback

When OpenSearch is not configured or the request fails, `google_drive.search_drive(q)` is called. It performs a Google Drive API query:

```
(name contains '<q>' or fullText contains '<q>') and trashed = false
```

Results come directly from the Drive API and do not include popularity scoring or HTML highlighting.

---

## Query Parameters

| Parameter  | Default          | Description                                         |
|------------|------------------|-----------------------------------------------------|
| `q`        | *(empty)*        | Search query. Accepts OpenSearch `query_string` syntax. |
| `size`     | `20`             | Number of results to return.                        |
| `index`    | `library-docs`   | OpenSearch index name. Overrides `OPENSEARCH_INDEX`.|
| `operator` | `or`             | Boolean operator for multi-term queries (`and`/`or`).|

The default operator can also be set globally via `OPENSEARCH_DEFAULT_OPERATOR`.

---

## Environment Variables

| Variable                       | Default        | Description                                   |
|--------------------------------|----------------|-----------------------------------------------|
| `OPENSEARCH_URL`               | *(none)*       | Base URL of the OpenSearch cluster            |
| `OPENSEARCH_USERNAME`          | *(none)*       | HTTP Basic Auth username                      |
| `OPENSEARCH_PASSWORD`          | *(none)*       | HTTP Basic Auth password                      |
| `OPENSEARCH_TLS_CA`            | *(none)*       | PEM certificate (inline or base64) for TLS    |
| `OPENSEARCH_INDEX`             | `library-docs` | Default index name                            |
| `OPENSEARCH_DEFAULT_OPERATOR`  | `or`           | Default boolean operator for `query_string`   |
| `OPENSEARCH_POPULARITY_WEIGHT` | `0.001`        | Popularity boost factor (set to `0` to disable) |

---

## Template

Results are rendered via `templates/search.html` with the following context variables:

| Variable             | Description                                      |
|----------------------|--------------------------------------------------|
| `search_results`     | List of result objects (see Result Shape above)  |
| `doc_reference_dict` | Navigation reference dictionary                  |
| `query`              | The original query string                        |
| `TARGET_DRIVE`       | Google Drive ID (for constructing Drive links)   |
| `navigation`         | Full navigation hierarchy                        |
| `previous_slug`      | Empty string (suppresses active-page highlighting)|
| `used_opensearch`    | `True` if OpenSearch was used, `False` otherwise |

---

## OpenSearch Index Mappings

The `library-docs` index is created (if absent) with these field mappings:

| Field              | Type      | Notes                              |
|--------------------|-----------|------------------------------------|
| `path`             | `keyword` | Unique document path               |
| `owner`            | `keyword` |                                    |
| `type`             | `keyword` |                                    |
| `doc_metadata`     | `object`  | Nested JSON metadata               |
| `headings_map`     | `object`  | Heading structure                  |
| `full_html`        | `text`    | Full HTML content, used for search |
| `views`            | `integer` | Analytics: total page views        |
| `sessions`         | `integer` | Analytics: total sessions          |
| `engaged_sessions` | `integer` | Analytics: engaged sessions        |
