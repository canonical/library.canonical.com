import io
import os

from flask import abort

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO

from datetime import datetime, timedelta

TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv("URL_FILE", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg")
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
            print(f"{err}\n {error}")
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
            print(f"{err}\n {error}")
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
            print(f"{err}\n {error}")
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
            print(f"{err}\n {error}")
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
            print(f"{err}\n {error}")
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
            print(f"{err}\n {error}")
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

    def get_document(self, document_id):
        if self.cache.get(document_id) is not None:
            docInfo = self.cache.get("docDic")[document_id]
            cachedDoc = self.cache.get(document_id)
            dateformat = "%Y-%m-%dT%H:%M:%S.%fZ"
            date = cachedDoc["lastFetch"]
            cachedDocDate = datetime.strptime(date, dateformat)
            if docInfo["modifiedTime"] > cachedDoc["modifiedTime"]:
                return self.fetch_document(document_id)
            elif (datetime.today() - cachedDocDate).days >= MAX_CACHE_AGE:
                return self.fetch_document(document_id)
            else:
                return cachedDoc["html"]
        else:
            return self.fetch_document(document_id)

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
                docs = self.cache.get("docDic")
                info = {
                    "id": document_id,
                    "html": html,
                    "modifiedTime": docs[document_id]["modifiedTime"],
                    "lastFetch": datetime.today().strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                }
                self.cache.set(document_id, info)
                return html
            else:
                err = "Error, document not found."
                print(f"{err}\n")
                abort(404, description=err)

        except Exception as error:
            err = "Error retrieving HTML or caching document."
            print(f"{err}\n {error}")
            abort(500, description=err)

    def fetch_spreadsheet(self, document_id):
        try:
            request = self.service.files().export(
                fileId=document_id, mimeType="text/csv"
            )

            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                _, done = downloader.next_chunk()
            csv = file.getvalue().decode("utf-8")

            if csv:
                return csv
            else:
                err = "Error, document not found."
                print(f"{err}\n")
                abort(404, description=err)

        except Exception as error:
            err = "Error retrieving HTML or caching document."
            print(f"{err}\n {error}")
            abort(500, description=err)
