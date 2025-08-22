from webapp.app import app, get_urls_expiring_soon, warm_cache_for_urls

# Global state variables
cache_warming_in_progress = False
cache_updated = False

def worker_url_cache_warming():
    """
    Background worker to check for expiring cache entries and warm them.
    """
    global cache_warming_in_progress
    global cache_updated

    if not cache_warming_in_progress:
        print("\n\nChecking cache status...\n\n")
        expiring_urls = get_urls_expiring_soon()
        cache_warming_in_progress = True
        urls_to_warm = [u["url"] for u in expiring_urls]
        warm_cache_for_urls(urls_to_warm)
        cache_warming_in_progress = False
        cache_updated = True

if __name__ == "__main__":
    with app.app_context():
        worker_url_cache_warming()