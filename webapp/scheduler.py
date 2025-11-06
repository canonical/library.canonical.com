import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

import webapp.state as state
from webapp.services.navigation_service import construct_navigation_data
from webapp.services.cache_warm import get_urls_expiring_soon, warm_cache_for_urls
from webapp.services.drive_service import get_google_drive_instance
from webapp.navigation_builder import NavigationBuilder
from webapp.services.spreadsheet_service import GoggleSheet
from webapp.googledrive import GoogleDrive
from webapp.extensions import cache
from webapp.db import db
from webapp.services.document_service import get_or_parse_document
from webapp.models import Document

ROOT = os.getenv("ROOT_FOLDER", "library")


def process_changes(changes, navigation_data, google_drive):
    """Process Drive changes and set url_updated when paths change."""
    new_nav = NavigationBuilder(google_drive, ROOT)
    for change in changes:
        if change.get("removed"):
            print("REMOVED")
        else:
            if "fileId" in change and navigation_data:
                if change["fileId"] in navigation_data.doc_reference_dict:
                    nav_item = navigation_data.doc_reference_dict[change["fileId"]]
                    new_nav_item = new_nav.doc_reference_dict[change["fileId"]]
                    if nav_item.get("full_path") != new_nav_item.get("full_path"):
                        old_path = nav_item["full_path"][1:]
                        new_path = new_nav_item["full_path"][1:]
                        GoggleSheet(old_path, new_path).update_urls()
                        state.url_updated = True
    return new_nav


def scheduled_get_changes():
    """Fetch and process Drive changes, updating state.nav_changes."""
    google_drive = state.gdrive_instance
    changes = google_drive.get_latest_changes()
    state.nav_changes = process_changes(changes, state.nav_changes, state.gdrive_instance)

## Top-level scheduled_clean_cache removed; defined inside init_scheduler to avoid importing app and circulars


def init_scheduler(app, document_fn):
    """Initialize the background scheduler for periodic tasks."""

    def scheduled_task():
        with app.app_context():
            google_drive = state.gdrive_instance
            navigation = state.nav_changes
            changes = google_drive.get_latest_changes()
            new_nav = process_changes(changes, navigation, google_drive)
            state.nav_changes = new_nav

    def check_status_cache():
        # Defer cache status work until assets exist (check in warm function)
        # Delete the old url_list.txt if it exists
        url_list_path = os.path.join(app.static_folder, "assets", "url_list.txt")
        if os.path.exists(url_list_path):
            os.remove(url_list_path)
            print(f"Deleted old {url_list_path}")

        with app.app_context():
            construct_navigation_data()
        if not state.cache_warming_in_progress:
            print("\n\nChecking cache status...\n\n")
            expiring_urls = get_urls_expiring_soon(app)
            if expiring_urls:
                print(f"Found {len(expiring_urls)} URLs expiring, warming cache")
                state.cache_warming_in_progress = True
                urls_to_warm = [u["url"] for u in expiring_urls]
                warm_cache_for_urls(urls_to_warm, app, construct_navigation_data, document_fn)
                state.cache_warming_in_progress = False
                state.cache_updated = True
            else:
                print("No URLs expiring soon, no action taken.")

    def ingest_all_documents_job():
        if "POSTGRESQL_DB_CONNECT_STRING" not in os.environ:
            print("DB not configured; skipping ingest job", flush=True)
            return

        workers = int(os.getenv("INGEST_WORKERS", "10"))

        with app.app_context():
            try:
                try:
                    nav = construct_navigation_data()
                except Exception:
                    # build or fetch from cache
                    nav = get_google_drive_instance()

                doc_dict = getattr(nav, "doc_reference_dict", {}) or {}
                items = list(doc_dict.items())
                total = len(items)
                if total == 0:
                    print("[ingest] nothing to ingest", flush=True)
                    return

                created = 0
                skipped = 0
                errors = 0

                def _ingest_one(args):
                    doc_id, meta = args
                    with app.app_context():
                        try:
                            drive = GoogleDrive(cache)
                            # Fast skip if exists
                            if db.session.query(Document.id).filter_by(google_drive_id=doc_id).first():
                                return "skipped", doc_id, None
                            # Parse and persist
                            get_or_parse_document(drive, doc_id, doc_dict, meta.get("name", ""))
                            return "created", doc_id, None
                        except IntegrityError:
                            db.session.rollback()
                            return "skipped", doc_id, None
                        except Exception as e:
                            db.session.rollback()
                            return "error", doc_id, str(e)
                        finally:
                            db.session.remove()

                print(f"[ingest] starting {total} docs with {workers} workers", flush=True)
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    for status, doc_id, err in ex.map(_ingest_one, items):
                        if status == "created":
                            created += 1
                        elif status == "skipped":
                            skipped += 1
                        else:
                            errors += 1
                            print(f"[ingest] error id={doc_id}: {err}", flush=True)
                print(f"[ingest] done created={created} skipped={skipped} errors={errors} total={total}", flush=True)
            except Exception as e:
                print(f"[ingest] fatal error: {e}", flush=True)

    def scheduled_clean_cache():
        if not os.getenv("REDIS_DB_CONNECT_STRING"):
            print("[cache] Redis not configured; skipping cache clean", flush=True)
            return

        # Clear root and navigation first
        cache.delete("view//")
        cache.delete("navigation")

        removed = 0
        url_file_path = os.path.join(app.static_folder, "assets", "url_list.txt")
        if not os.path.exists(url_file_path):
            # Build navigation now (this recreates url_list.txt)
            with app.app_context():
                try:
                    construct_navigation_data()
                except Exception as e:
                    print(f"[cache] failed to construct navigation for url_list.txt: {e}", flush=True)
            # Re-check for the file after construction
            if not os.path.exists(url_file_path):
                print(f"[cache] url_list.txt not found at {url_file_path} after rebuild", flush=True)
                return

        with open(url_file_path, "r") as f:
            for line in f:
                url = line.strip()
                if not url:
                    continue
                path = url.lstrip("/")
                key = f"view//{path}"
                if cache.delete(key):
                    removed += 1

        print(f"[cache] cleared {removed} view entries from url_list", flush=True)


    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task)  # Run once
    # Build navigation/cache status (once), and clean cache immediately after
    scheduler.add_job(check_status_cache)  # Run once on load
    scheduler.add_job(scheduled_clean_cache)  # Run once on load
    scheduler.add_job(ingest_all_documents_job)  # Run on load
    scheduler.add_job(scheduled_task, "interval", minutes=5)
    scheduler.add_job(check_status_cache, trigger="cron", day_of_week="sun", hour=7, minute=0)
    scheduler.add_job(ingest_all_documents_job, "interval", hours=6)
    scheduler.start()
    return scheduler
