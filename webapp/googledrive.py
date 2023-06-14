import io
import os

from flask import abort

from pymemcache.client.base import Client
from cachetools import TTLCache

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO

TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")

cache = TTLCache(maxsize=100, ttl=1800)


class Drive:
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
        self.client = Client(("localhost", 11211))

    # @cached(cache)
    def get_document_list(self):
        try:
            results = (
                self.service.files()
                .list(
                    q="trashed=false",
                    corpora="teamDrive",
                    supportsTeamDrives=True,
                    includeItemsFromAllDrives=True,
                    teamDriveId=TARGET_DRIVE,
                    spaces="drive",
                    fields="nextPageToken, "
                    "files(id, name, parents, mimeType)",
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
            # html = self.client.get(document_id)
            # if html is not None:
            #     return html.decode("utf-8")

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
                # self.client.set(document_id, html.encode("utf-8"))
                return html
            else:
                err = "Error, document not found."
                print(f"{err}\n")
                abort(404, description=err)

        except Exception as error:
            err = "Error retrieving HTML or caching document."
            print(f"{err}\n {error}")
            abort(500, description=err)
