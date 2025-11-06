import os
from flask import g

from webapp.services.drive_service import get_google_drive_instance


def get_list_of_urls():
    """
    Fetch the redirects spreadsheet (old -> new URLs) from Google Drive and
    cache it in flask.g as 'list_of_urls'.
    """
    google_drive = get_google_drive_instance()
    urls = []

    url_doc = os.getenv(
        "URL_FILE",
        "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg",  # default used in app
    )
    print("FETCHING SPREADSHEET", flush=True)
    print("URL_DOC", url_doc, flush=True)

    csv_text = google_drive.fetch_spreadsheet(url_doc)
    # Skip header row
    lines = csv_text.split("\n")[1:]
    for line in lines:
        parts = line.split(",")
        if not parts or len(parts) < 2:
            continue
        urls.append({"old": parts[0], "new": parts[1].replace("\r", "")})

    g.list_of_urls = urls


def find_broken_url(url: str):
    """
    Given an 'old' URL, return its mapped 'new' URL if present in the list.
    """
    if "list_of_urls" not in g:
        get_list_of_urls()
    for u in g.list_of_urls:
        if u["old"] == url:
            return u["new"]
    return None
