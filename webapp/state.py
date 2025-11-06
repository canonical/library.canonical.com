# Centralized mutable application state.
# Keeping module-level attributes to preserve existing semantics.

nav_changes = None
url_updated = False
gdrive_instance = None
initialized_executed = False
cache_warming_in_progress = False
cache_navigation_data = None
cache_updated = False
