import io
import os

from flask import abort

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO

TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")


class GoogleDrive:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )

    def search_drive(self, query):
        try:
            query_string = f"(name contains '{query}' or fullText contains '{query}') and trashed = false"
            print("query sting>>>", query_string)
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
        print("items length>>>",len(items))
        return items

    def get_document_list(self):
        try:
            results = (
                self.service.files()
                .list(
                    q="trashed=false",
                    corpora="drive",
                    driveId=TARGET_DRIVE,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    spaces="drive",
                    fields="files(id, name, parents, mimeType, owners)",
                    pageSize=1000,
                )
                .execute()
            )
        except Exception as error:
            err = "Error fetching document list."
            print(f"{err}\n {error}")
            abort(500, description=err)

        items = results.get("files", [])
        return items

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
                print(f"{err}\n")
                abort(404, description=err)

        except Exception as error:
            err = "Error retrieving HTML or caching document."
            print(f"{err}\n {error}")
            abort(500, description=err)
