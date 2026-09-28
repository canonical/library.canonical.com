# Navigation Functions

Navigation functions live in `webapp/app.py` and are responsible for building, caching, and querying the site's hierarchical document tree.

---

## `get_navigation_data()`

Returns the `NavigationBuilder` instance for the current request.

**Resolution order:**

1. If `g.navigation_data` is already set on the current request context, return it directly.
2. If `session["navigation_data_cached"]` is set, attempt to read the navigation from the Redis/simple cache under the key `"navigation"`.
   - On a cache hit, reconstructs a `NavigationBuilder` from the cached data without re-querying Google Drive.
   - On a cache miss, falls through to `construct_navigation_data()`.
3. If neither condition is met, calls `construct_navigation_data()`.

The result is always stored in `g.navigation_data` for reuse within the same request.

---

## `construct_navigation_data()`

Builds the navigation tree from scratch by querying Google Drive.

1. Creates a `GoogleDrive` instance via `get_google_drive_instance()`.
2. Instantiates `NavigationBuilder(google_drive, ROOT, hide_folder=HIDE_FOLDER)`.
3. Serialises the result (`doc_reference_dict`, `temp_hierarchy`, `file_list`, `hierarchy`) and stores it in the cache under the key `"navigation"`.
4. Sets `session["navigation_data_cached"] = True` when inside a request context.

Returns the `NavigationBuilder` instance.

---

## `get_target_document(path, navigation)`

Traverses the navigation hierarchy to find and mark the document matching `path`.

- `path`: URL path string (e.g. `"section/sub-section/page"`).
- `navigation`: the `hierarchy` dict from `NavigationBuilder`.

**Traversal logic:**

- An empty `path` marks `navigation["index"]` as active and returns it.
- Otherwise, the path is split by `/` and each segment is used as a key into the nested `children` dicts.
- The final segment's node is marked `active = True`.
- All intermediate folder nodes are marked `expanded = True`.
- If the final node is a folder, it returns the folder's `children["index"]` node instead.

Raises `KeyError` if any path segment is not found (caller catches this and checks the redirect table).

---

## `reset_navigation_flags(navigation)`

Recursively resets the `active` and `expanded` flags to `False` on all nodes in the navigation tree.

Called at the start of each request (before `get_target_document`) to ensure a clean state, since the cached navigation tree may have flags set from a previous request.

---

## Navigation Data in the Document Route

The `document(path)` view applies additional logic before delegating to the functions above:

| Condition                        | Action                                             |
|----------------------------------|----------------------------------------------------|
| `cache_updated` is `True`        | Calls `construct_navigation_data()` and resets the flag. |
| `url_updated` and cache not warming | Calls `construct_navigation_data()` and resets the flag. |
| `cache_warming_in_progress`      | Uses `copy.deepcopy(cache_navigation_data)` to avoid mutating the shared warming copy. |
| Otherwise                        | Calls `get_navigation_data()`.                     |

After navigation is obtained, `reset_navigation_flags` is always called before `get_target_document`.

---

## Cache Keys

| Key            | Contents                                                  |
|----------------|-----------------------------------------------------------|
| `"navigation"` | Dict with `doc_reference_dict`, `temp_hierarchy`, `file_list`, `hierarchy` |
| `"view//<path>"` | Cached rendered HTML for each document path            |

---

## Global State Variables Related to Navigation

| Variable                    | Type   | Description                                                  |
|-----------------------------|--------|--------------------------------------------------------------|
| `nav_changes`               | `NavigationBuilder` | Last known navigation state, updated by the scheduler. |
| `cache_navigation_data`     | `NavigationBuilder` | Navigation snapshot used during cache warming.         |
| `cache_warming_in_progress` | `bool` | `True` while the cache-warming thread is running.       |
| `cache_updated`             | `bool` | Set to `True` by the warming thread when it finishes.   |
| `url_updated`               | `bool` | Set to `True` when a document path change is detected.  |

---

## Environment Variables

| Variable      | Default     | Description                                                 |
|---------------|-------------|-------------------------------------------------------------|
| `ROOT_FOLDER` | `library`   | Slug of the root folder in Google Drive.                   |
| `HIDE_FOLDER` | `true`      | When `true`, hides the test/development folder from the tree. |
