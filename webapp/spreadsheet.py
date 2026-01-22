import os

from flask import abort

from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO


TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv(
    "URL_DOC", "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg"
    )
MAX_CACHE_AGE = 14


class GoggleSheet:
    def __init__(self, old_url, new_url):
        self.old_url = old_url
        self.new_url = new_url
        scopes = [
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO, scopes=scopes
        )
        self.service = build(
            "sheets", "v4", credentials=credentials, cache_discovery=False
        )

    def update_urls(self):
        try:
            # Append data to the spreadsheet
            data_to_append = [[self.old_url, self.new_url]]
            append_request = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=URL_DOC,
                    range="A:B",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": data_to_append},
                )
            )
            append_request.execute()
        except Exception as error:
            err = "Error fetching spreadsheet."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
        return self.old_url, self.new_url
