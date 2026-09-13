# Navigation Builder

The `NavigationBuilder` class lives in `webapp/navigation_builder.py`. It is responsible for transforming the flat list of files returned by the Google Drive API into a nested hierarchy that drives the site navigation.

---

## Construction Modes

The constructor accepts two modes controlled by the `cache` parameter.

### Fresh build (`cache=False`, default)

```python
NavigationBuilder(google_drive, root_folder, hide_folder=False)
```

1. Fetches a deep copy of the full file list from Google Drive via `get_file_list_copy`.
2. Calls `initialize_reference_dict` to build `doc_reference_dict` (a flat `{id: doc}` map).
3. Calls `create_hierarchy` to nest the flat list into a tree.
4. Calls `update_references_dict` to refresh `doc_reference_dict` with the fully resolved tree nodes (which now include `full_path` and other enriched fields).
5. Calls `save_urls_to_file` to write all URLs to `static/assets/url_list.txt`.

### From cache (`cache=True`)

```python
NavigationBuilder(
    google_drive, root_folder,
    cache=True,
    doc_reference_dict=...,
    temp_hierarchy=...,
    file_list=...,
    hierarchy=...,
    hide_folder=False,
)
```

Skips Google Drive and the build pipeline entirely. Accepts pre-built data structures and applies the `remove_folder` filter if `hide_folder=True`, then calls `save_urls_to_file`.

---

## Instance Attributes

| Attribute            | Type   | Description                                                    |
|----------------------|--------|----------------------------------------------------------------|
| `root_folder`        | `str`  | Lowercased root folder slug (e.g. `"library"`)                 |
| `file_list`          | `list` | Deep copy of raw file objects from Google Drive                |
| `doc_reference_dict` | `dict` | Flat `{google_drive_id: doc_node}` map (updated after hierarchy build) |
| `temp_hierarchy`     | `dict` | Intermediate hierarchy starting from the root folder node     |
| `hierarchy`          | `dict` | Final hierarchy: the children of the root folder node          |

---

## Methods

### `get_file_list_copy(google_drive) → list`

Calls `google_drive.get_document_list()` and returns a deep copy. The deep copy prevents the Drive cache from being mutated during tree construction.

---

### `create_reference_dict(doc_objects) → dict`

Builds the initial flat reference dictionary from the raw Drive file list.

For each file:

- Orphan documents (no `parents` field) are assigned `parents = None`.
- `children` is initialised to an empty dict.
- `mimeType` is simplified to the part after the last `.` (e.g. `"folder"`, `"document"`).
- Leading numbers are extracted into `position` and stripped from `name`.
- `isSoftRoot` is set to `True` if the name contains `!`; the `!` is then removed.
- `/` in names is replaced with `-`.
- `slug` is derived by lowercasing the name and replacing spaces with `-`.
- `active` and `expanded` flags are initialised to `False`.
- Only files whose parent ID is longer than 20 characters (i.e. a real Drive folder, not the drive root) or whose name matches the root folder are included.

---

### `create_hierarchy(doc_objects, hide_folder) → dict`

Nests the flat file list into a tree by placing each document under its parent's `children` dict.

- Traverses `doc_objects` and looks up the parent in `doc_reference_dict`.
- The root folder node is placed at the top level in `temp_hierarchy`.
- Documents whose parent is not found (orphaned or outside the root) are removed from `doc_reference_dict`.
- Calls `add_path_context` to enrich every node with `full_path` and `breadcrumbs`.
- Aborts with HTTP 503 if the root folder is not found in the resulting tree.
- Returns `temp_hierarchy[root_folder]["children"]` (optionally filtered by `remove_folder`).

---

### `insert_based_on_position(parent_obj, doc)`

Appends a child document to a parent's `children` dict and re-sorts the children.

Sort key: `(position, slug.lower())` — documents with a numeric prefix come first in numeric order; documents without a prefix are sorted alphabetically after those with one.

---

### `add_path_context(hierarchy_obj, path="", breadcrumbs=None)`

Recursively adds two fields to every node:

| Field         | Type   | Description                                                       |
|---------------|--------|-------------------------------------------------------------------|
| `full_path`   | `str`  | Absolute URL path (e.g. `/section/sub-section/page`)             |
| `breadcrumbs` | `list` | List of `{"name": ..., "path": ...}` dicts for ancestor nodes    |

The root folder node and `index` nodes are given the parent's path (they do not add a new path segment).

---

### `update_references_dict(hierarchy_obj) → dict`

Rebuilds `doc_reference_dict` from the fully constructed hierarchy so that all nodes (including folders) are indexed by their Google Drive ID, with all enriched fields (`full_path`, `breadcrumbs`, etc.) present.

---

### `remove_folder(hierarchy) → dict`

Removes the excluded test/development folder from the hierarchy.

The excluded path is hardcoded as:
```
about-the-library/tests-and-issues-(for-development-purpose)
```

Navigates to the parent folder and deletes the target slug from `children`.

---

### `extract_all_urls(hierarchy_obj=None, urls=None) → set`

Recursively collects all non-empty `full_path` values from the hierarchy into a set. Folder nodes are traversed into their `children`.

---

### `save_urls_to_file()`

Writes the set of all URL paths to `static/assets/url_list.txt` (one URL per line).

Skips saving if the file already exists. This file is consumed by:

- `get_urls_expiring_soon()` — to determine which URLs need cache warming.
- `restore-cleared-cached` route — to know which URLs to re-warm.
- `clear-all-views` route — to know which cache keys to clear.

---

## Hierarchy Node Structure

Each node in the hierarchy is a dict with these fields after the full build:

| Field          | Type     | Description                                        |
|----------------|----------|----------------------------------------------------|
| `id`           | `str`    | Google Drive file ID                               |
| `name`         | `str`    | Display name (leading numbers and `!` removed)     |
| `slug`         | `str`    | URL-safe lowercase name with spaces as `-`         |
| `mimeType`     | `str`    | `"folder"` or `"document"`                        |
| `parents`      | `list`   | Parent folder IDs (or `None` for orphans)          |
| `position`     | `int` \| `None` | Sort position extracted from leading number |
| `isSoftRoot`   | `bool`   | `True` if the name originally contained `!`        |
| `active`       | `bool`   | `True` when this node is the current page          |
| `expanded`     | `bool`   | `True` when this node is an ancestor of the current page |
| `children`     | `dict`   | Nested child nodes (folders and documents)         |
| `full_path`    | `str`    | Absolute URL path                                  |
| `breadcrumbs`  | `list`   | Ancestor breadcrumb list                           |

---

## Excluded Folder

The folder at:
```
about-the-library/tests-and-issues-(for-development-purpose)
```
is always removed from the hierarchy when `HIDE_FOLDER=true` (the default). It is also filtered from search results in the search route.
