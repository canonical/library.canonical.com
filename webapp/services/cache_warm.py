import os
import copy
from concurrent.futures import ThreadPoolExecutor
from flask import g

import webapp.state as state
from webapp.services.navigation_service import construct_navigation_data


def get_urls_expiring_soon(app):
    """Return list of URLs (dicts with 'url') from assets/url_list.txt.

    This mirrors the existing behavior (no TTL inspection unless Redis is used)
    but keeps file I/O in one place. The caller can decide how to use it.
    """
    expiring_urls = []
    url_file_path = os.path.join(app.static_folder, "assets", "url_list.txt")
    if not os.path.exists(url_file_path):
        print("URL list file not found.")
        return expiring_urls

    with open(url_file_path, "r") as f:
        urls = [line.strip() for line in f if line.strip()]
    for url in urls:
        expiring_urls.append({"url": url})
    return expiring_urls


def warm_single_url(app, url: str, navigation_data, document_fn) -> None:
    """Warm cache for a single URL by simulating a request context.

    document_fn: callable like document(path) (to avoid circular import)
    """
    try:
        path = url.lstrip("/")
        nav_copy = copy.deepcopy(navigation_data)
        print(f"Warming cache for {url} with path {path}")
        with app.test_request_context(f"/{path}"):
            g.navigation_data = nav_copy
            document_fn(path)
    except Exception as e:
        print(f"Error warming cache for {url}: {e}")


def warm_cache_for_urls(urls, app, construct_navigation_data_fn=construct_navigation_data, document_fn=None) -> None:
    """Warm cache for a list of URLs in parallel.

    - Skips work until assets_ready() is True to avoid caching pages that link
      to missing CSS bundles during first boot.
    - Accepts the document function to avoid importing app.py.
    """
    if document_fn is None:
        raise ValueError("document_fn is required to render pages during warm")

    navigation_data = construct_navigation_data_fn()
    state.cache_navigation_data = navigation_data

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(
            lambda url: warm_single_url(app, url, navigation_data, document_fn),
            urls,
        )
    print(f"\n\n Finished cache warming for {len(urls)} URLs. \n\n")
