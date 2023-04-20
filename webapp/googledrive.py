import io

from flask import abort

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO


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

    def get_document_list(self):
        try:
            results = (
                self.service.files()
                .list(
                    q="trashed=false",
                    corpora="allDrives",
                    supportsTeamDrives=True,
                    includeItemsFromAllDrives=True,
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

    def get_html(self, document_id):
        try:
            request = self.service.files().export(
                fileId=document_id, mimeType="text/html"
            )
        except Exception as error:
            err = "Error, document not found."
            print(f"{err}\n {error}")
            abort(404, description=err)

        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        html = file.getvalue().decode("utf-8")

        return html
