from flask import g
from webapp.extensions import cache
from webapp.googledrive import GoogleDrive


def get_google_drive_instance():
    """Return a singleton GoogleDrive bound to Flask's request context.

    Stores the instance on flask.g to reuse within a single request and
    across helpers that rely on it.
    """
    if "google_drive" not in g:
        g.google_drive = GoogleDrive(cache)
    return g.google_drive
