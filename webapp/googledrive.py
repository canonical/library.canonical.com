import io
import os

from flask import abort

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from webapp.settings import SERVICE_ACCOUNT_INFO

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv("URL_FILE", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg")
DEFAULT_DOC = os.getenv(
    "DEFAULT_DOC", "1YxnWy94YrNnraf1OAxXfIAbL677nNjvb-AWp1TaxU9s"
)
DRAFT_FOLDER = os.getenv("DRAFT_FOLDER", "1cI2ClDWDzv3osp0Adn0w3Y7zJJ5h08ua")
MAX_CACHE_AGE = 14


class GoogleDrive:
    def __init__(self, cache):
        scopes = [
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )
        self.cache = cache

    def search_drive(self, query):
        try:
            query_string = (
                f"(name contains '{query}' or fullText contains '{query}') "
                "and trashed = false"
            )

            results = (
                self.service.files()
                .list(
                    q=query_string,
                    corpora="drive",
                    driveId=TARGET_DRIVE,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    spaces="drive",
                    fields="files(id, name, mimeType, description)",
                    pageSize=1000,
                )
                .execute()
            )

        except Exception as error:
            err = "Error searching for documents."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)

        items = results.get("files", [])
        return items

    # Added the next page token to be able to obtain the whole list of files
    # in the drive, since when the fields contains files(..., parents)
    # the maximum number of files that can be obtained is 460.
    def get_document_list(self):
        next_page_token = ""
        items = []
        fields = (
            "nextPageToken, files(id, name, mimeType, parents, owners, "
            "modifiedTime)"
        )
        try:
            while (next_page_token is not None) or (next_page_token == ""):
                results = (
                    self.service.files()
                    .list(
                        q="trashed=false",
                        corpora="drive",
                        driveId=TARGET_DRIVE,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        spaces="drive",
                        fields=fields,
                        pageSize=1000,
                        pageToken=next_page_token,
                    )
                    .execute()
                )
                items.extend(results.get("files", []))
                next_page_token = results.get("nextPageToken", None)
        except Exception as error:
            err = "Error fetching document list."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
        for item in items:
            if item["id"] == URL_DOC:
                items.remove(item)
                break
        docDic = {}
        for item in items:
            docDic[item["id"]] = item
        self.cache.set("docDic", docDic)
        return items

    def get_changes(self):
        next_page_token = ""
        try:
            tokens = self.service.changes().getStartPageToken().execute()
            next_page_token = tokens.get("startPageToken")
        except Exception as error:
            err = "Error Fetching Start Page Token."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
        items = []
        try:
            while (next_page_token is not None) or (next_page_token == ""):
                results = (
                    self.service.changes()
                    .list(
                        driveId=TARGET_DRIVE,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        includeCorpusRemovals=True,
                        includeRemoved=True,
                        pageSize=1000,
                        pageToken=next_page_token,
                        restrictToMyDrive=False,
                        spaces="drive",
                        includePermissionsForView="published",
                        includeLabels=True,
                    )
                    .execute()
                )
                items.extend(results.get("changes", []))
                next_page_token = results.get("nextPageToken", None)
        except Exception as error:
            err = "Error Fetching Changes."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
        return items

    def get_latest_changes(self):
        next_page_token = self.cache.get("startPageToken")
        try:
            if not next_page_token:
                tokens = self.service.changes().getStartPageToken().execute()
                next_page_token = tokens.get("startPageToken")
        except Exception as error:
            err = "Error Fetching Start Page Token."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
        items = []
        last_usable_token = None
        try:
            while next_page_token:
                results = (
                    self.service.changes()
                    .list(
                        driveId=TARGET_DRIVE,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        includeCorpusRemovals=True,
                        includeRemoved=True,
                        pageSize=1000,
                        pageToken=next_page_token,
                        restrictToMyDrive=False,
                        spaces="drive",
                        includePermissionsForView="published",
                        includeLabels=True,
                    )
                    .execute()
                )
                items.extend(results.get("changes", []))
                if results.get("nextPageToken", None) is None:
                    last_usable_token = next_page_token
                next_page_token = results.get("nextPageToken", None)
        except Exception as error:
            err = "Error Fetching Changes."
            print(f"{err}\n {error}, flush=True")
            abort(500, description=err)

        # Store the latest startPageToken for future use
        if next_page_token is None:
            self.cache.set("startPageToken", last_usable_token)
        # Filter changes from the last 5 minutes
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_changes = []
        for item in items:
            change_time = datetime.strptime(
                item["time"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            if change_time > five_minutes_ago:
                recent_changes.append(item)

        return recent_changes

    def fetch_document(self, document_id):
        try:
            request = self.service.files().export(
                fileId=document_id, mimeType="text/html"
            )
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                _, done = downloader.next_chunk()
            html = file.getvalue().decode("utf-8")

            if html:
                return html
            else:
                err = "Error, document not found."
                print(f"{err}\n", flush=True)
                abort(404, description=err)

        except HttpError as error:
            details = error.error_details or []
            reasons = [d.get("reason") for d in details if isinstance(d, dict)]
            if "exportSizeLimitExceeded" in reasons:
                logger.warning(
                    "File %s too large for Drive export API, "
                    "falling back to Docs API.",
                    document_id,
                )
                return self._fetch_document_via_docs_api(document_id)
            skip_reasons = {"fileNotExportable", "internalError"}
            if skip_reasons.intersection(reasons):
                raise ValueError(
                    f"File {document_id} cannot be exported: {', '.join(reasons)}"
                ) from error
            err = "Error retrieving HTML or caching document."
            print(f"{err} | Exception: {error}", flush=True)
            abort(500, description=error)
        except Exception as error:
            err = "Error retrieving HTML or caching document."
            print(f"{err} | Exception: {error}", flush=True)
            abort(500, description=error)

    def _build_docs_service(self):
        scopes = ["https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        return build(
            "docs", "v1", credentials=credentials, cache_discovery=False
        )

    def _docs_api_to_html(self, document):
        """Convert a Google Docs API document JSON to a minimal HTML string."""

        def text_run_to_html(text_run):
            text = text_run.get("content", "")
            if text == "\n":
                return ""
            style = text_run.get("textStyle", {})
            if style.get("bold"):
                text = f"<strong>{text}</strong>"
            if style.get("italic"):
                text = f"<em>{text}</em>"
            if style.get("underline"):
                text = f"<u>{text}</u>"
            return text

        def paragraph_to_html(paragraph):
            heading_map = {
                "HEADING_1": "h1",
                "HEADING_2": "h2",
                "HEADING_3": "h3",
                "HEADING_4": "h4",
                "HEADING_5": "h5",
                "HEADING_6": "h6",
            }
            style_type = paragraph.get("paragraphStyle", {}).get(
                "namedStyleType", "NORMAL_TEXT"
            )
            tag = heading_map.get(style_type, "p")
            inner = "".join(
                text_run_to_html(elem["textRun"])
                for elem in paragraph.get("elements", [])
                if "textRun" in elem
            )
            if not inner.strip():
                return ""
            return f"<{tag}>{inner}</{tag}>"

        parts = []
        for block in document.get("body", {}).get("content", []):
            if "paragraph" in block:
                html = paragraph_to_html(block["paragraph"])
                if html:
                    parts.append(html)
            elif "table" in block:
                rows = []
                for row in block["table"].get("tableRows", []):
                    cells = []
                    for cell in row.get("tableCells", []):
                        cell_html = "".join(
                            paragraph_to_html(cb["paragraph"])
                            for cb in cell.get("content", [])
                            if "paragraph" in cb
                        )
                        cells.append(f"<td>{cell_html}</td>")
                    rows.append(f"<tr>{''.join(cells)}</tr>")
                parts.append(f"<table>{''.join(rows)}</table>")

        body = "".join(parts)
        return f'<html><body class="doc-content">{body}</body></html>'

    def _fetch_document_via_docs_api(self, document_id):
        docs_service = self._build_docs_service()
        document = (
            docs_service.documents().get(documentId=document_id).execute()
        )
        return self._docs_api_to_html(document)

    def fetch_spreadsheet(self, document_id):
        print("Fetching spreadsheet", document_id, flush=True)
        try:

            request = self.service.files().export(
                fileId=document_id, mimeType="text/csv"
            )

            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                print("Downloading chunk...", flush=True)
                _, done = downloader.next_chunk()
            csv = file.getvalue().decode("utf-8")
            print("Download complete", flush=True)
            print("CSV content:", csv[:100], flush=True)  # Log first 100 chars
            if csv:
                return csv
            else:
                err = "Error, document not found."
                print(f"{err}\n", flush=True)
                abort(404, description=err)

        except Exception as error:
            err = "Error retrieving SPREADSHEET "
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)

    def create_copy_template(self, name):
        try:
            file_metadata = {
                "name": "Template Copy-" + name,
                "title": "Template Copy-" + name,
                "description": "Copy of Template Document",
                "mimeType": "application/vnd.google-apps.document",
                "parents": [DRAFT_FOLDER],
            }

            file = (
                self.service.files()
                .copy(
                    fileId=DEFAULT_DOC,
                    body=file_metadata,
                    supportsAllDrives=True,
                    ignoreDefaultVisibility=True,
                )
                .execute()
            )

            print("Template copy created successfully.")
            print(f"File ID: {file.get('id')}")
            return file.get("id")
        except Exception as error:
            err = "Error creating copy of Template."
            print(f"{err}\n {error}", flush=True)
            # abort(500, description=err)
            return None

    def get_changes_last_week(self):
        """
        Get all changes from the last week in the shared drive.
        Returns a list of changed file IDs.
        """
        try:
            # Get the start page token from a week ago
            one_week_ago = datetime.utcnow() - timedelta(days=7)

            # Get initial page token
            tokens = self.service.changes().getStartPageToken().execute()
            next_page_token = tokens.get("startPageToken")

            items = []
            try:
                while next_page_token:
                    results = (
                        self.service.changes()
                        .list(
                            driveId=TARGET_DRIVE,
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True,
                            includeCorpusRemovals=True,
                            includeRemoved=True,
                            pageSize=1000,
                            pageToken=next_page_token,
                            restrictToMyDrive=False,
                            spaces="drive",
                            includePermissionsForView="published",
                            includeLabels=True,
                        )
                        .execute()
                    )
                    items.extend(results.get("changes", []))
                    next_page_token = results.get("nextPageToken", None)
            except Exception as error:
                print(f"Error fetching changes: {error}", flush=True)
                return []

            # Filter changes from the last week
            recent_changes = []
            for item in items:
                try:
                    change_time = datetime.strptime(
                        item["time"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    if change_time > one_week_ago:
                        recent_changes.append(item)
                except (KeyError, ValueError) as e:
                    print(f"Error parsing change time: {e}", flush=True)
                    continue

            # Extract unique file IDs that were modified (not removed)
            modified_files = []
            for change in recent_changes:
                if not change.get("removed", False) and "file" in change:
                    file_info = change["file"]
                    # Only include Google Docs (not folders)
                    if (
                        file_info.get("mimeType")
                        == "application/vnd.google-apps.document"
                    ):
                        modified_files.append(
                            {
                                "id": file_info["id"],
                                "name": file_info.get("name", "Unknown"),
                                "modifiedTime": change.get("time"),
                                "owners": file_info.get("owners", []),
                            }
                        )

            # Remove duplicates by file ID
            seen = set()
            unique_files = []
            for file in modified_files:
                if file["id"] not in seen:
                    seen.add(file["id"])
                    unique_files.append(file)

            return unique_files

        except Exception as error:
            err = "Error fetching last week's changes."
            print(f"{err}\n {error}", flush=True)
            return []

    def get_document_comments(self, document_id):
        """
        Get all comments for a specific document.
        Returns a list of comments with their resolved status.
        """
        try:
            results = (
                self.service.comments()
                .list(
                    fileId=document_id,
                    fields="comments(id,content,resolved,author,createdTime,replies)",
                    includeDeleted=False,
                )
                .execute()
            )

            comments = results.get("comments", [])
            return comments

        except Exception as error:
            print(
                f"Error fetching comments for {document_id}: {error}",
                flush=True,
            )
            return []

    def get_unresolved_comments_count(self, document_id):
        """
        Get the count of unresolved comments for a specific document.
        """
        comments = self.get_document_comments(document_id)
        unresolved_count = sum(
            1 for comment in comments if not comment.get("resolved", False)
        )
        return unresolved_count
