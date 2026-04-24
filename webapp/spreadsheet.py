import os

from flask import abort

from googleapiclient.discovery import build
from google.oauth2 import service_account

from webapp.settings import SERVICE_ACCOUNT_INFO


TARGET_DRIVE = os.getenv("TARGET_DRIVE", "0ABG0Z5eOlOvhUk9PVA")
URL_DOC = os.getenv(
    "URL_DOC",
    "16mTPcMn9hxjgra62ArjL6sTg75iKiqsdN99vtmrlyLg",
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
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
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

    @staticmethod
    def fetch_analytics_data(sheet_id, sheet_tab="Sheet1", start_row=16):
        """
        Fetch analytics data from a Google Sheet.
        
        Args:
            sheet_id: The Google Sheet ID
            sheet_tab: The tab/sheet name (default: "Sheet1")
            start_row: The row number where data starts (default: 16)
            
        Returns:
            List of rows from the sheet (including header row at start_row)
            
        Raises:
            Exception: If there's an error fetching the data
        """
        try:
            # Initialize Sheets API client
            scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
            credentials = service_account.Credentials.from_service_account_info(
                SERVICE_ACCOUNT_INFO, scopes=scopes
            )
            sheets_service = build(
                "sheets", "v4", credentials=credentials, cache_discovery=False
            )

            # Fetch data starting from the specified row
            # Columns: A=pagePath, B=views, C=sessions, D=engagedSessions
            range_name = f"{sheet_tab}!A{start_row}:D"
            result_data = (
                sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range_name)
                .execute()
            )
            
            rows = result_data.get("values", [])
            return rows
            
        except Exception as error:
            err = "Error fetching analytics data from spreadsheet."
            print(f"{err}\n {error}", flush=True)
            abort(500, description=err)
