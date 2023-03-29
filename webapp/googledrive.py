import io

from apiclient.http import MediaIoBaseDownload
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO


class Drive:
    def __init__(self):
        scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        self.service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )

    def get_first_10_documents(self):
        """GETs the first 10 items availiable to the service account"""

        try:
            results = (
                self.service.files()
                .list(pageSize=10, fields="nextPageToken, files(id, name)")
                .execute()
            )
            items = results.get("files", [])
        except HttpError as error:
            print(f"An error occurred: {error}")

        return items

    def get_html(self, document_id):
        """GETs a specific document based off its ID"""
        request = self.service.files().export(
            fileId=document_id, mimeType="text/html"
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()
        html = fh.getvalue().decode("utf-8")

        return html
